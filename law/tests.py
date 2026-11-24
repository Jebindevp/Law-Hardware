from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
import json
import re

from .models import Category, Product, Bill, BillItem, Brand, FeaturedOfferProduct


class PlumbingBillingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name="PVC Pipes & Fittings",
            description="High quality PVC pipes and fittings"
        )
        self.product1 = Product.objects.create(
            category=self.category,
            name="PVC Elbow 90 Degree",
            size="25mm",
            rate=Decimal("45.00"),
            quantity=100
        )
        self.product2 = Product.objects.create(
            category=self.category,
            name="CPVC Pipe Schedule 40",
            size="1 inch x 3m",
            rate=Decimal("350.00"),
            quantity=50
        )

    def test_product_total_and_low_stock(self):
        """Verify product total and low stock alert calculations."""
        self.assertEqual(self.product1.total, Decimal("4500.00"))
        self.assertFalse(self.product1.is_low_stock)

        low_product = Product.objects.create(
            category=self.category,
            name="Ball Valve",
            size="1/2 inch",
            rate=Decimal("120.00"),
            quantity=5
        )
        self.assertTrue(low_product.is_low_stock)

    def test_bill_number_auto_generation(self):
        """Verify bill number format: Capital letters + 6-digit number."""
        bill = Bill.objects.create(
            customer_name="Ramesh Kumar",
            customer_phone="9876543210",
            gender="MALE",
            door_no="12/A",
            address="Gandhi Street, Town Center",
            id_proof_type="AADHAAR",
            id_proof_number="1234-5678-9012",
            subtotal=Decimal("1000.00"),
            grand_total=Decimal("1180.00"),
            paid_amount=Decimal("1180.00"),
        )
        self.assertTrue(bill.bill_number.startswith("JEB-"))
        pattern = r"^JEB-[A-Z]{3}\d{6}$"
        self.assertTrue(re.match(pattern, bill.bill_number), f"Bill number {bill.bill_number} does not match pattern")
        self.assertEqual(bill.gender_icon, "👨")
        self.assertEqual(bill.id_proof_label, "Aadhaar Card")

    def test_five_tier_payment_statuses(self):
        """Verify 5-tier payment status calculation logic."""
        # 1. 100% Completed Paid
        bill_full = Bill.objects.create(
            customer_name="Customer 100%",
            grand_total=Decimal("1000.00"),
            paid_amount=Decimal("1000.00")
        )
        self.assertEqual(bill_full.payment_status, "COMPLETED_PAID")
        self.assertEqual(bill_full.balance_amount, Decimal("0.00"))

        # Overpaid also completed paid
        bill_over = Bill.objects.create(
            customer_name="Customer Overpaid",
            grand_total=Decimal("1000.00"),
            paid_amount=Decimal("1200.00")
        )
        self.assertEqual(bill_over.payment_status, "COMPLETED_PAID")
        self.assertEqual(bill_over.balance_amount, Decimal("0.00"))

        # 2. 80%+ High Paid (e.g. 850 paid out of 1000)
        bill_80 = Bill.objects.create(
            customer_name="Customer 85%",
            grand_total=Decimal("1000.00"),
            paid_amount=Decimal("850.00")
        )
        self.assertEqual(bill_80.payment_status, "HIGH_80_PAID")
        self.assertEqual(bill_80.balance_amount, Decimal("150.00"))

        # 3. 50%+ High Paid (e.g. 600 paid out of 1000)
        bill_50 = Bill.objects.create(
            customer_name="Customer 60%",
            grand_total=Decimal("1000.00"),
            paid_amount=Decimal("600.00")
        )
        self.assertEqual(bill_50.payment_status, "HIGH_50_PAID")
        self.assertEqual(bill_50.balance_amount, Decimal("400.00"))

        # 4. 50% Down Paid (e.g. 300 paid out of 1000)
        bill_down = Bill.objects.create(
            customer_name="Customer 30%",
            grand_total=Decimal("1000.00"),
            paid_amount=Decimal("300.00")
        )
        self.assertEqual(bill_down.payment_status, "DOWN_50_PAID")
        self.assertEqual(bill_down.balance_amount, Decimal("700.00"))

        # 5. No Paid (0% paid)
        bill_none = Bill.objects.create(
            customer_name="Customer 0%",
            grand_total=Decimal("1000.00"),
            paid_amount=Decimal("0.00")
        )
        self.assertEqual(bill_none.payment_status, "NO_PAID")
        self.assertEqual(bill_none.balance_amount, Decimal("1000.00"))

    def test_create_bill_api(self):
        """Verify create_bill_api creates bill with customer details, ID proof, GST, and inventory reduction."""
        payload = {
            "customer_name": "Kavitha Sundaram",
            "customer_phone": "9841023456",
            "gender": "FEMALE",
            "door_no": "45-B",
            "address": "South Car Street, Hardware Nagar",
            "id_proof_type": "PAN",
            "id_proof_number": "ABCDE1234F",
            "payment_mode": "UPI",
            "discount": 50.0,
            "gst_rate": 18.0,
            "paid_amount": 300.0,
            "notes": "Delivered to construction site",
            "items": [
                {
                    "product_id": self.product1.id,
                    "product_name": self.product1.name,
                    "size": self.product1.size,
                    "category": self.category.name,
                    "rate": 45.0,
                    "quantity": 10
                }
            ]
        }

        response = self.client.post(
            reverse('create_bill_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertEqual(res_data['status'], 'success')
        self.assertIn('bill_number', res_data)

        # Verify DB bill state
        bill = Bill.objects.get(bill_number=res_data['bill_number'])
        self.assertEqual(bill.customer_name, "Kavitha Sundaram")
        self.assertEqual(bill.customer_phone, "9841023456")
        self.assertEqual(bill.gender, "FEMALE")
        self.assertEqual(bill.gender_icon, "👩")
        self.assertEqual(bill.door_no, "45-B")
        self.assertEqual(bill.id_proof_type, "PAN")
        self.assertEqual(bill.id_proof_number, "ABCDE1234F")

        # Subtotal = 10 * 45 = 450.00
        # Discount = 50.00 -> Taxable = 400.00
        # GST (18%) = 72.00 -> Total = 472.00
        # Paid = 300.00 -> Balance = 172.00
        # Ratio = 300 / 472 = ~63.5% -> HIGH_50_PAID
        self.assertEqual(float(bill.subtotal), 450.00)
        self.assertEqual(float(bill.discount), 50.00)
        self.assertEqual(float(bill.gst_amount), 72.00)
        self.assertEqual(float(bill.grand_total), 472.00)
        self.assertEqual(float(bill.paid_amount), 300.00)
        self.assertEqual(float(bill.balance_amount), 172.00)
        self.assertEqual(bill.payment_status, "HIGH_50_PAID")

        # Verify product quantity reduction
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.quantity, 90)

    def test_invoices_list_view(self):
        """Verify invoices list context and stats rendering."""
        Bill.objects.create(
            customer_name="Test Buyer",
            grand_total=Decimal("500.00"),
            paid_amount=Decimal("500.00"),
            payment_status="COMPLETED_PAID"
        )
        response = self.client.get(reverse('invoices_list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('completed_paid_count', response.context)
        self.assertIn('high_80_count', response.context)
        self.assertIn('high_50_count', response.context)
        self.assertIn('down_50_count', response.context)
        self.assertIn('no_paid_count', response.context)
        self.assertIn('total_paid', response.context)
        self.assertIn('total_balance', response.context)


    def test_featured_offer_apis_and_index_view(self):
        """Verify featured offer add, update, and delete APIs and homepage rendering."""
        from .models import FeaturedOfferProduct

        # 1. Add featured offer API
        add_payload = {
            "name": "Brass Bib Tap Premium Test",
            "category_name": "Taps & Faucets",
            "size": "1/2 inch",
            "image_url": "https://example.com/tap.jpg",
            "original_price": 400.0,
            "discount_price": 280.0,
            "offer_date": "31 Dec 2026",
            "description": "Chrome finish heavy duty bib cock tap.",
            "button_text": "Add to Bill",
            "button_link": "/pos/",
            "order": 1
        }
        res_add = self.client.post(
            reverse('add_featured_offer_api'),
            data=json.dumps(add_payload),
            content_type='application/json'
        )
        self.assertEqual(res_add.status_code, 200)
        offer_id = res_add.json().get('offer_id')
        self.assertTrue(offer_id)

        # 2. Update featured offer API
        update_payload = {
            "name": "Brass Bib Tap Premium Test",
            "category_name": "Taps & Faucets",
            "size": "1/2 inch",
            "image_url": "https://example.com/tap_updated.jpg",
            "original_price": 450.0,
            "discount_price": 299.0,
            "offer_date": "15 Jan 2027",
            "description": "Updated chrome finish bib cock tap."
        }
        res_update = self.client.post(
            reverse('update_featured_offer_api', kwargs={'offer_id': offer_id}),
            data=json.dumps(update_payload),
            content_type='application/json'
        )
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.json()['status'], 'success')

        # Verify DB update
        offer = FeaturedOfferProduct.objects.get(id=offer_id)
        self.assertEqual(float(offer.discount_price), 299.0)

        # 3. Check homepage rendering (Anonymous visitor sees View Details & Booking mobile +91 77086 23440)
        res_home = self.client.get(reverse('index'))
        self.assertEqual(res_home.status_code, 200)
        html = res_home.content.decode('utf-8')
        self.assertIn("77086 23440", html)
        self.assertIn("Lawrence C", html)
        self.assertNotIn('{{ shop_owner|default:"Lawrence C"', html)
        self.assertIn("btn-product-view", html)

        # 4. Delete featured offer API
        res_del = self.client.post(
            reverse('delete_featured_offer_api', kwargs={'offer_id': offer_id})
        )
        self.assertEqual(res_del.status_code, 200)
        self.assertFalse(FeaturedOfferProduct.objects.filter(id=offer_id).exists())

    def test_invoice_print_view_clean_rendering(self):
        """Verify invoice print view renders without customer gender emojis."""
        bill = Bill.objects.create(
            customer_name="Walk-in Customer",
            customer_phone="",
            gender="MALE",
            grand_total=Decimal("200.00"),
            paid_amount=Decimal("200.00"),
            payment_status="COMPLETED_PAID"
        )
        BillItem.objects.create(
            bill=bill,
            product=self.product1,
            product_name=self.product1.name,
            category_name=self.category.name,
            size="25mm",
            rate=Decimal("45.00"),
            quantity=2,
            total=Decimal("90.00")
        )
        # Test default and GST mode (type=gst)
        response = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}) + '?type=gst')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn("Walk-in Customer", html)
        self.assertIn("33CGSPC1805K1ZG", html)
        self.assertIn("Mulagumoodu Junction", html)
        self.assertIn("TAX INVOICE", html)
        self.assertIn("mode-gst", html)
        self.assertIn("CGST", html)

        # Test Non-GST mode (type=nogst)
        response_nogst = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}) + '?type=nogst')
        self.assertEqual(response_nogst.status_code, 200)
        html_nogst = response_nogst.content.decode('utf-8')
        self.assertIn("RETAIL BILL", html_nogst)
        self.assertIn("mode-nogst", html_nogst)
        # Ensure 'Retail Cash Memo (Non-GST)' is NOT shown as requested by user
        self.assertNotIn("Retail Cash Memo (Non-GST)", html_nogst)
        # Ensure discount amount is NOT shown in print statement
        self.assertNotIn("Discount:", html)
        self.assertNotIn("Discount:", html_nogst)

    def test_brand_and_pipe_length_calculation(self):
        """Verify Brand management, pipe length, 1-meter rate & full pipe price calculation."""
        # 1. Create Brand
        brand = Brand.objects.create(
            name="Finolex",
            description="Premium PVC and CPVC Pipes"
        )
        self.assertEqual(brand.product_count, 0)

        # 2. Create METER product (Length Pipe)
        pipe = Product.objects.create(
            category=self.category,
            brand=brand,
            product_code="PIPE-110",
            name="Finolex Pasting Pipe 110mm",
            size="110mm 6kg/cm",
            unit="METER",
            pipe_length=Decimal("6.00"),
            rate=Decimal("581.00"),
            quantity=30  # 30 meters = 5 pipes
        )
        self.assertEqual(pipe.display_brand, "Finolex")
        self.assertEqual(pipe.full_pipe_price, Decimal("3486.00"))
        self.assertEqual(pipe.estimated_pipe_count, 5)

        # 3. Test Brand API endpoints
        # Add Brand API
        res_brand = self.client.post(
            reverse('add_brand_api'),
            data=json.dumps({'name': 'Ashirvad Pipes', 'description': 'CPVC FlowGuard'}),
            content_type='application/json'
        )
        self.assertEqual(res_brand.status_code, 200)
        data_b = json.loads(res_brand.content)
        self.assertEqual(data_b['status'], 'success')
        new_brand_id = data_b['brand_id']

        # Edit Brand API
        res_edit_b = self.client.post(
            reverse('edit_brand_api', kwargs={'brand_id': new_brand_id}),
            data=json.dumps({'name': 'Ashirvad CPVC', 'description': 'Updated'}),
            content_type='application/json'
        )
        self.assertEqual(res_edit_b.status_code, 200)
        self.assertEqual(Brand.objects.get(id=new_brand_id).name, 'Ashirvad CPVC')

        # 4. Add Product API with brand and pipe length
        res_prod = self.client.post(
            reverse('add_product_api'),
            data=json.dumps({
                'category_id': self.category.id,
                'brand_id': new_brand_id,
                'product_code': 'ASH-50',
                'name': 'Ashirvad 50mm Pipe',
                'size': '50mm',
                'unit': 'METER',
                'pipe_length': 3.00,
                'rate': 250.00,
                'quantity': 60
            }),
            content_type='application/json'
        )
        self.assertEqual(res_prod.status_code, 200)
        data_p = json.loads(res_prod.content)
        self.assertEqual(data_p['status'], 'success')
        self.assertEqual(data_p['full_pipe_price'], 750.00)

        # 5. Verify admindashboard and inventory contexts include brands
        resp_admin = self.client.get(reverse('admindashboard'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn('brands', resp_admin.context)

        resp_inv = self.client.get(reverse('inventory'))
        self.assertEqual(resp_inv.status_code, 200)
        self.assertIn('brands', resp_inv.context)

    def test_pipe_lengths_and_meters_billing_and_print(self):
        """
        Verify pipe items calculation (1 Length Pipe = 6.00 meters = 20 feet),
        POS billing breakdown, stock deduction, and clear print display.
        """
        # Create a PVC Pipe sold by meters with standard 6m length
        pipe_cat = Category.objects.create(name="PVC Pipes", description="Pipes")
        pipe_prod = Product.objects.create(
            category=pipe_cat,
            name="Finolex Pasting Pipe",
            size="110 mm - 4",
            unit="METER",
            pipe_length=Decimal("6.00"),
            rate=Decimal("581.00"),
            quantity=60  # 60 meters in stock (= 10 full pipes)
        )

        # 1. Test 1 Length Pipe pricing
        self.assertEqual(pipe_prod.pipe_length, Decimal("6.00"))
        self.assertEqual(pipe_prod.full_pipe_price, Decimal("3486.00"))

        # 2. Bill 2 full lengths of pipe (= 12.00 meters, 40 feet)
        payload = {
            "customer_name": "Antony Raj",
            "customer_phone": "9876501234",
            "gender": "MALE",
            "door_no": "5/139/1",
            "address": "Mulagumoodu Junction",
            "payment_mode": "CASH",
            "discount": 0.0,
            "gst_rate": 18.0,
            "paid_amount": 8226.96,
            "items": [
                {
                    "product_id": pipe_prod.id,
                    "quantity": 12.0,  # 2 lengths * 6.00m = 12 meters
                    "size": "110 mm - 4 • 2 Len (12m/40ft)"
                }
            ]
        }
        res = self.client.post(
            reverse('create_bill_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        res_data = res.json()
        self.assertEqual(res_data['status'], 'success')
        bill_id = res_data['bill_id']

        # 3. Verify BillItem pipe breakdown calculations
        bill = Bill.objects.get(id=bill_id)
        item = bill.items.first()
        self.assertIsNotNone(item)
        self.assertTrue(item.is_pipe)
        self.assertEqual(item.pipe_std_len, 6.00)
        self.assertEqual(item.pipe_lengths, 2)
        self.assertEqual(item.pipe_meters, 12.0)
        self.assertEqual(item.pipe_feet, 40)
        self.assertEqual(item.pipe_display, "2 Lengths = 12.00 Meters (40 Feet)")

        # Verify stock was deducted from 60 meters to 48 meters
        pipe_prod.refresh_from_db()
        self.assertEqual(pipe_prod.quantity, 48)

        # 4. Verify Invoice Print view renders detailed length, meter, and feet breakdowns
        print_res = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}) + '?type=gst')
        self.assertEqual(print_res.status_code, 200)
        html = print_res.content.decode('utf-8')
        self.assertIn("2 Lengths</strong> = 12.00 Meters (approx. 40 Feet)", html)
        self.assertIn("Standard: 1 Length Pipe = 6.00 Meters (approx. 20 Feet)", html)
        self.assertIn("2 <span style=\"font-size: 10px; color: #64748b;\">len</span>", html)
        self.assertIn("(12.0m)", html)
        self.assertIn("/meter", html)

        # 5. Verify Invoices List view contains length and meter badges
        list_res = self.client.get(reverse('invoices_list'))
        self.assertEqual(list_res.status_code, 200)
        list_html = list_res.content.decode('utf-8')
        self.assertIn("2 Lengths (12.0m / 40ft)", list_html)

    def test_inventory_fitting_vs_pipe_add_api(self):
        """
        Verify that adding fittings (unit=PIECE) does not assign pipe length/meters,
        while only pipe products (unit=METER) store pipe lengths (e.g. 6.00m).
        """
        # 1. Add Fitting (Elbow) - unit: PIECE
        res_fitting = self.client.post(
            reverse('add_product_api'),
            data=json.dumps({
                'category_id': self.category.id,
                'name': 'PVC 90 Degree Elbow Fitting',
                'size': '25mm',
                'unit': 'PIECE',
                'pipe_length': 6.00,  # Even if sent, backend sets 1.00 for fittings
                'rate': 35.00,
                'quantity': 50
            }),
            content_type='application/json'
        )
        self.assertEqual(res_fitting.status_code, 200)
        fitting_id = res_fitting.json()['product_id']
        fitting = Product.objects.get(id=fitting_id)

        # Fittings should be PIECE with standard 1.00 unit, not 6.00m pipe
        self.assertEqual(fitting.unit, 'PIECE')
        self.assertEqual(fitting.pipe_length, Decimal('1.00'))
        self.assertFalse(fitting.is_meter)
        self.assertFalse(fitting.is_pipe)
        self.assertEqual(fitting.rate_display, '₹35.00 / pc')
        self.assertEqual(fitting.full_pipe_price, 35.00)

        # 2. Add Pipe - unit: METER
        res_pipe = self.client.post(
            reverse('add_product_api'),
            data=json.dumps({
                'category_id': self.category.id,
                'name': 'PVC Rigid Conduit Pipe',
                'size': '25mm x 6m',
                'unit': 'METER',
                'pipe_length': 6.00,
                'rate': 80.00,
                'quantity': 60  # 60 meters = 10 pipes
            }),
            content_type='application/json'
        )
        self.assertEqual(res_pipe.status_code, 200)
        pipe_id = res_pipe.json()['product_id']
        pipe = Product.objects.get(id=pipe_id)

        # Pipes should be METER with standard 6.00m pipe length
        self.assertEqual(pipe.unit, 'METER')
        self.assertEqual(pipe.pipe_length, Decimal('6.00'))
        self.assertTrue(pipe.is_meter)
        self.assertTrue(pipe.is_pipe)
        self.assertEqual(pipe.rate_display, '₹80.00 / meter')
        self.assertEqual(pipe.full_pipe_price, 480.00)  # 6m * 80
        self.assertEqual(pipe.estimated_pipe_count, 10.0)

    def test_pos_billing_fittings_vs_pipes_separation(self):
        """
        Verify that in POS billing, fittings (even in categories with 'Pipe' in the name)
        are billed purely as pieces without meter/length badges, while only genuine pipes
        show length and meter calculations on the bill and print invoice.
        """
        # Use self.category which is "PVC Pipes & Fittings"
        cat = self.category
        
        # 1. Elbow Fitting (Piece)
        elbow = Product.objects.create(
            category=cat,
            name="PVC Elbow 90deg",
            size="25mm",
            unit="PIECE",
            pipe_length=Decimal("1.00"),
            rate=Decimal("35.00"),
            quantity=100
        )
        self.assertFalse(elbow.is_pipe)

        # 2. Pipe (Meter / Length)
        pipe = Product.objects.create(
            category=cat,
            name="PVC Pasting Pipe 6kg",
            size="110mm",
            unit="METER",
            pipe_length=Decimal("6.00"),
            rate=Decimal("581.00"),
            quantity=60
        )
        self.assertTrue(pipe.is_pipe)

        # 3. Create Bill via API with both items
        payload = {
            "customer_name": "Murugan Hardware",
            "customer_phone": "9876543210",
            "gender": "MALE",
            "payment_mode": "CASH",
            "gst_rate": 18.0,
            "items": [
                {
                    "product_id": elbow.id,
                    "quantity": 5.0,
                    "size": elbow.size  # Pure size for fitting
                },
                {
                    "product_id": pipe.id,
                    "quantity": 12.0,  # 2 lengths = 12m
                    "size": "110mm • 2 Len (12m/40ft)"
                }
            ]
        }
        res = self.client.post(
            reverse('create_bill_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        bill_id = res.json()['bill_id']
        bill = Bill.objects.get(id=bill_id)

        # 4. Verify line items
        elbow_item = bill.items.get(product_id=elbow.id)
        pipe_item = bill.items.get(product_id=pipe.id)

        # Fitting item MUST NOT be pipe
        self.assertFalse(elbow_item.is_pipe)
        self.assertEqual(elbow_item.pipe_display, "")
        self.assertEqual(elbow_item.size, "25mm")

        # Pipe item MUST be pipe
        self.assertTrue(pipe_item.is_pipe)
        self.assertEqual(pipe_item.pipe_lengths, 2)
        self.assertEqual(pipe_item.pipe_meters, 12.0)
        self.assertEqual(pipe_item.pipe_feet, 40)

        # 5. Verify Invoice Print view renders length badges for pipe but NOT for elbow
        print_res = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}))
        self.assertEqual(print_res.status_code, 200)
        html = print_res.content.decode('utf-8')

        # Pipe length badge is rendered
        self.assertIn("2 Lengths</strong> = 12.00 Meters", html)
        self.assertIn("(12.0m)", html)

        # Elbow fitting is rendered with standard pieces, not length badges
        self.assertIn("PVC Elbow 90deg", html)
        self.assertNotIn("PVC Elbow 90deg</strong>\n                        <div style=\"font-size: 11.5px; color: #64748b;\">PVC Pipes & Fittings</div>\n                        \n                        <div style=\"margin-top: 4px;", html)

    def test_billing_pos_size_filter_and_toolbar(self):
        """
        Verify that billing_pos passes unique sorted sizes to context,
        and renders both the size dropdown and quick size filter pills in the catalog toolbar.
        """
        # Create test products with varied sizes
        Product.objects.create(
            category=self.category,
            name="CPVC Pipe SDR 11",
            size="3/4 inch",
            unit="METER",
            pipe_length=Decimal("3.00"),
            rate=Decimal("120.00"),
            quantity=50
        )
        Product.objects.create(
            category=self.category,
            name="UPVC Brass Tee",
            size="1 inch",
            unit="PIECE",
            rate=Decimal("95.00"),
            quantity=40
        )

        res = self.client.get(reverse('billing_pos'))
        self.assertEqual(res.status_code, 200)

        # Context contains unique sizes
        self.assertIn('sizes', res.context)
        sizes = res.context['sizes']
        self.assertIn('3/4 inch', sizes)
        self.assertIn('1 inch', sizes)

        html = res.content.decode('utf-8')
        # Check size dropdown and quick filter pills
        self.assertIn('id="posSizeFilter"', html)
        self.assertIn('onchange="onPosSizeDropdownChange()"', html)
        self.assertIn('class="pos-size-bar"', html)
        self.assertIn('class="pos-size-pill', html)
        self.assertIn('selectPosSize(', html)

    def test_partial_payment_balance_amount_in_pos_and_print(self):
        """
        Verify that balance amounts are accurately calculated and displayed:
        1. On the billing_pos screen in the live summary card
        2. On the invoice_print page for both GST and Non-GST views
        """
        # 1. Check POS billing page has live paid and balance due in summary card
        pos_res = self.client.get(reverse('billing_pos'))
        self.assertEqual(pos_res.status_code, 200)
        pos_html = pos_res.content.decode('utf-8')
        self.assertIn('id="cardSummaryPaid"', pos_html)
        self.assertIn('id="cardSummaryBalance"', pos_html)

        # 2. Create a bill with partial payment (Grand Total: 750, Paid: 500, Balance: 250)
        bill = Bill.objects.create(
            customer_name="Kannan Electricals",
            customer_phone="9876501234",
            payment_mode="SPLIT",
            subtotal=Decimal("750.00"),
            discount=Decimal("0.00"),
            gst_rate=Decimal("0.00"),
            gst_amount=Decimal("0.00"),
            grand_total=Decimal("750.00"),
            paid_amount=Decimal("500.00"),
            balance_amount=Decimal("250.00")
        )
        BillItem.objects.create(
            bill=bill,
            product=self.product1,
            product_name="PVC Pipe 110mm",
            category_name="PVC Pipes",
            size="110mm",
            rate=Decimal("750.00"),
            quantity=1,
            total=Decimal("750.00")
        )

        # 3. Verify in Non-GST Print view
        res_nogst = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}) + '?type=nogst')
        self.assertEqual(res_nogst.status_code, 200)
        html_nogst = res_nogst.content.decode('utf-8')
        self.assertIn("500.00", html_nogst)
        self.assertIn("250.00", html_nogst)

        # 4. Verify in GST Print view
        res_gst = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}) + '?type=gst')
        self.assertEqual(res_gst.status_code, 200)
        html_gst = res_gst.content.decode('utf-8')
        self.assertIn("500.00", html_gst)
        self.assertIn("250.00", html_gst)

    def test_invoices_list_json_data_and_edit_invoice_api(self):
        """
        Verify that:
        1. invoices_list template provides #allBillsJsonData with serialized bills & line items.
        2. edit_invoice_api updates line items, rates, quantities, customer details, and recalculates totals.
        """
        bill = Bill.objects.create(
            customer_name="Murugan Stores",
            customer_phone="9443322110",
            gender="MALE",
            door_no="88/1",
            address="Main Bazaar",
            id_proof_type="AADHAAR",
            id_proof_number="9988-7766-5544",
            payment_mode="CASH",
            subtotal=Decimal("900.00"),
            discount=Decimal("0.00"),
            gst_rate=Decimal("18.00"),
            gst_amount=Decimal("162.00"),
            grand_total=Decimal("1062.00"),
            paid_amount=Decimal("1062.00"),
            balance_amount=Decimal("0.00")
        )
        item = BillItem.objects.create(
            bill=bill,
            product=self.product1,
            product_name="PVC Elbow 90 Degree",
            category_name="PVC Pipes & Fittings",
            size="25mm",
            rate=Decimal("45.00"),
            quantity=20,
            total=Decimal("900.00")
        )

        # 1. Verify invoices_list page contains the serialized JSON script
        res_list = self.client.get(reverse('invoices_list'))
        self.assertEqual(res_list.status_code, 200)
        self.assertIn('bills_dict', res_list.context)
        self.assertIn(str(bill.id), res_list.context['bills_dict'])
        bill_data = res_list.context['bills_dict'][str(bill.id)]
        self.assertEqual(bill_data['customer_name'], "Murugan Stores")
        self.assertEqual(len(bill_data['items']), 1)
        self.assertEqual(bill_data['items'][0]['product_name'], "PVC Elbow 90 Degree")
        self.assertEqual(bill_data['items'][0]['quantity'], 20.0)

        html = res_list.content.decode('utf-8')
        self.assertIn('id="allBillsJsonData"', html)
        self.assertIn('openEditInvoiceModal', html)
        self.assertIn('String(currentEditingBill.id) !== targetId', html)

        # 2. Test edit_invoice_api with modified qty and new item
        edit_payload = {
            "customer_name": "Murugan Hardware & Electricals",
            "customer_phone": "9443322110",
            "gender": "MALE",
            "door_no": "88/1A",
            "address": "Main Bazaar Road",
            "id_proof_type": "AADHAAR",
            "id_proof_number": "9988-7766-5544",
            "payment_mode": "UPI",
            "discount": 50.0,
            "gst_rate": 18.0,
            "paid_amount": 1000.0,
            "notes": "Updated after site delivery",
            "items": [
                {
                    "id": item.id,
                    "product_id": self.product1.id,
                    "product_name": self.product1.name,
                    "category_name": self.category.name,
                    "size": self.product1.size,
                    "rate": 45.0,
                    "quantity": 10
                },
                {
                    "product_id": self.product2.id,
                    "product_name": self.product2.name,
                    "category_name": self.category.name,
                    "size": self.product2.size,
                    "rate": 350.0,
                    "quantity": 2
                }
            ]
        }
        res_edit = self.client.post(
            reverse('edit_invoice_api', kwargs={'bill_id': bill.id}),
            data=json.dumps(edit_payload),
            content_type='application/json'
        )
        self.assertEqual(res_edit.status_code, 200)
        edit_resp = res_edit.json()
        self.assertEqual(edit_resp['status'], 'success')

        bill.refresh_from_db()
        self.assertEqual(bill.customer_name, "Murugan Hardware & Electricals")
        # Subtotal: (10 * 45) + (2 * 350) = 450 + 700 = 1150
        # Discount: 50 -> Taxable: 1100
        # GST (18%): 198.00 -> Grand Total: 1298.00
        # Paid: 1000.00 -> Balance: 298.00
        self.assertEqual(float(bill.subtotal), 1150.00)
        self.assertEqual(float(bill.discount), 50.00)
        self.assertEqual(float(bill.gst_amount), 198.00)
        self.assertEqual(float(bill.grand_total), 1298.00)
        self.assertEqual(float(bill.paid_amount), 1000.00)
        self.assertEqual(float(bill.balance_amount), 298.00)
        self.assertEqual(bill.items.count(), 2)

