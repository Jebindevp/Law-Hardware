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
        self.assertIn("Retail Cash Memo", html_nogst)

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
