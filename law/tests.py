from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
import json
import re

from .models import Category, Product, Bill, BillItem


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
        response = self.client.get(reverse('invoice_detail', kwargs={'bill_id': bill.id}))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn("Walk-in Customer", html)
        self.assertNotIn("<span>👨</span>", html)
        self.assertNotIn("<span>👩</span>", html)
        self.assertNotIn("📞 Mobile:", html)
