from django.db import models
from django.utils import timezone
from decimal import Decimal
import random
import string
import uuid


class Category(models.Model):
    """
    Category for plumbing and hardware items (e.g., PVC Pipes, Brass Fittings, Valves, Faucets).
    Managed dynamically by Admin.
    """
    name = models.CharField(max_length=120, unique=True, help_text="Category name (e.g., PVC Pipes, Brass Fittings)")
    description = models.TextField(blank=True, null=True, help_text="Brief description of the category")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def clean(self):
        super().clean()
        if self.name:
            stripped = self.name.strip()
            existing = Category.objects.filter(name__iexact=stripped)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'name': f'This category "{stripped}" is already added! Duplicate category is not allowed.'
                })

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.count()


class Brand(models.Model):
    """
    Brand / Manufacturer for plumbing items (e.g., Finolex, Ashirvad, Astral, Supreme, Prince, Jaquar, Watertec).
    Managed dynamically by Admin.
    """
    name = models.CharField(max_length=120, unique=True, help_text="Brand name (e.g., Finolex, Ashirvad, Astral, Supreme)")
    description = models.TextField(blank=True, null=True, help_text="Brief description or brand details")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"
        ordering = ['name']

    def clean(self):
        super().clean()
        if self.name:
            stripped = self.name.strip()
            existing = Brand.objects.filter(name__iexact=stripped)
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'name': f'This brand "{stripped}" is already added! Duplicate brand is not allowed.'
                })

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.count()


class Product(models.Model):
    """
    Product details: category, brand, ID number, name, unit (Piece vs Meter for pipes),
    pipe length (meters per pipe piece), size, rate, quantity, and total stock value.
    """
    UNIT_CHOICES = [
        ('PIECE', 'Piece / Unit (Nos)'),
        ('METER', 'Meter (m) / Length Pipe'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="Select product category"
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        help_text="Select product brand (e.g., Finolex, Ashirvad, Astral, Supreme)"
    )
    product_code = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Item ID / Code No",
        help_text="Unique Product/Item ID No (e.g. P-101, PIPE-25M, D00281103)"
    )
    name = models.CharField(max_length=200, help_text="Product name (e.g., CPVC Brass Elbow, Brass Ball Valve, PVC Pasting Pipe)")
    unit = models.CharField(
        max_length=20,
        choices=UNIT_CHOICES,
        default='PIECE',
        verbose_name="Pricing Unit",
        help_text="Piece / Unit or Length by Meter"
    )
    pipe_length = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=6.00,
        blank=True,
        null=True,
        verbose_name="Standard Pipe Length (Meters)",
        help_text="Standard length per pipe piece in meters (e.g., 6.0m, 3.0m)"
    )
    size = models.CharField(
        max_length=80,
        help_text="Size or dimension (e.g., 1/2\", 3/4\", 1\", 25mm, 110mm, 100m, Standard)"
    )
    rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Rate / Unit price or 1 Meter price in ₹ (e.g. 150.00, 581.00)"
    )
    quantity = models.PositiveIntegerField(
        default=0,
        help_text="Stock quantity available in store (Pieces or Total Meters)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['category', 'name', 'size']

    def clean(self):
        super().clean()
        if self.category and self.name and self.size:
            prod_name = self.name.strip()
            prod_size = self.size.strip()
            existing = Product.objects.filter(
                category=self.category,
                brand=self.brand,
                name__iexact=prod_name,
                size__iexact=prod_size
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                from django.core.exceptions import ValidationError
                brand_label = f" [{self.brand.name}]" if self.brand else ""
                raise ValidationError({
                    'name': f'This item "{prod_name}{brand_label} ({prod_size})" is already added in category "{self.category.name}"! Duplicate product is not allowed.'
                })

    def __str__(self):
        brand_str = f" [{self.brand.name}]" if self.brand else ""
        return f"{self.name}{brand_str} - {self.size} ({self.category.name})"

    @property
    def display_code(self):
        if self.product_code and self.product_code.strip():
            return self.product_code.strip()
        return f"P-{self.id:04d}" if self.id else "P-NEW"

    @property
    def display_brand(self):
        return self.brand.name if self.brand else "Generic / Standard"

    @property
    def is_meter(self):
        return self.unit == 'METER'

    @property
    def is_pipe(self):
        """Identifies if this product is a pipe sold by meters and length (not a fitting)"""
        if self.unit == 'METER':
            return True
        cname = (self.category.name if self.category else '').lower()
        pname = self.name.lower()
        fitting_keywords = ['elbow', 'tee', 'reducer', 'coupler', 'coupling', 'socket', 'union', 
                            'nipple', 'valve', 'cock', 'tap', 'faucet', 'clamp', 'bush', 'plug', 
                            'cap', 'bend', 'trap', 'collar', 'fitting', 'flange', 'adapter', 'solvent', 'cement']
        if any(kw in pname for kw in fitting_keywords) or any(kw in cname for kw in ['fitting', 'valve', 'tap', 'hardware']):
            return False
        return 'pipe' in cname or 'pipe' in pname

    @property
    def unit_label(self):
        return "meter" if self.unit == 'METER' else "pcs"

    @property
    def rate_display(self):
        if self.unit == 'METER':
            return f"₹{self.rate:.2f} / meter"
        return f"₹{self.rate:.2f} / pc"

    @property
    def full_pipe_price(self):
        """Price for 1 full standard length pipe (rate * pipe_length)"""
        if self.unit == 'METER' and self.pipe_length and self.pipe_length > 0:
            return round(float(self.rate) * float(self.pipe_length), 2)
        return float(self.rate)

    @property
    def estimated_pipe_count(self):
        """Estimated number of full pipes based on total stock meters / pipe_length"""
        if self.unit == 'METER' and self.pipe_length and self.pipe_length > 0 and self.quantity:
            return round(self.quantity / float(self.pipe_length), 1)
        return self.quantity

    @property
    def total(self):
        """Total inventory value = rate * quantity"""
        if self.rate is None or self.quantity is None:
            return 0.00
        return round(float(self.rate) * float(self.quantity), 2)

    @property
    def is_low_stock(self):
        if self.quantity is None:
            return False
        return self.quantity <= 10


class Bill(models.Model):
    """
    Customer invoice / bill record generated by the billing system.
    Shop Owner: Lawrence C
    """
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    ]

    ID_PROOF_CHOICES = [
        ('AADHAAR', 'Aadhaar Card'),
        ('PAN', 'PAN Card'),
        ('DRIVING_LICENCE', 'Driving Licence'),
        ('VOTER_ID', 'Voter ID'),
        ('SMART_CARD', 'Smart Card / Ration Card'),
        ('OTHER', 'Other ID'),
    ]

    PAYMENT_CHOICES = [
        ('CASH', 'Cash'),
        ('UPI', 'UPI / GPay / PhonePe / Paytm'),
        ('SPLIT', 'Split (Cash + UPI)'),
        ('CARD', 'Debit / Credit Card'),
        ('CREDIT', 'Credit / Due'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('COMPLETED_PAID', 'Completed Paid'),
        ('HIGH_80_PAID', '80%+ High Paid'),
        ('HIGH_50_PAID', '50%+ High Paid'),
        ('DOWN_50_PAID', '50% Down Paid'),
        ('NO_PAID', 'No Paid (Unpaid)'),
    ]

    # Auto-generated 6-digit number + Capital letters (e.g., JEB-KLP948201)
    bill_number = models.CharField(max_length=50, unique=True, editable=False)

    # Customer Information
    customer_name = models.CharField(max_length=150, default="Walk-in Customer")
    customer_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Mobile No")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='MALE')
    door_no = models.CharField(max_length=50, blank=True, null=True, verbose_name="Door / Flat No")
    address = models.TextField(blank=True, null=True, verbose_name="Address with Door No")
    id_proof_type = models.CharField(max_length=30, choices=ID_PROOF_CHOICES, default='AADHAAR')
    id_proof_number = models.CharField(max_length=60, blank=True, null=True, verbose_name="ID Proof No")

    # Payment & Financial Calculations
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='CASH')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Discount Amount")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00, verbose_name="GST Rate (%)")
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="GST Amount")
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total Amount")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Paid Amount")
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Balance Amount")
    payment_status = models.CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='COMPLETED_PAID')

    created_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Bill / Invoice"
        verbose_name_plural = "Bills / Invoices"
        ordering = ['-created_at']

    def calculate_payment_status(self):
        """
        Determines the payment status based on paid vs total ratio:
        1. 100% paid -> Completed Paid
        2. >=80% paid -> 80%+ High Paid
        3. >=50% paid -> 50%+ High Paid
        4. <50% paid  -> 50% Down Paid
        5. 0 paid     -> No Paid
        """
        total = float(self.grand_total or 0)
        paid = float(self.paid_amount or 0)
        self.balance_amount = Decimal(str(round(max(0.0, total - paid), 2)))

        if total <= 0:
            return 'COMPLETED_PAID'

        ratio = paid / total
        if ratio >= 1.0 or paid >= total:
            return 'COMPLETED_PAID'
        elif ratio >= 0.8:
            return 'HIGH_80_PAID'
        elif ratio >= 0.5:
            return 'HIGH_50_PAID'
        elif ratio > 0:
            return 'DOWN_50_PAID'
        else:
            return 'NO_PAID'

    def save(self, *args, **kwargs):
        # Generate bill number: 3 Capital Letters + 6-digit Number (e.g. JEB-KLP948201)
        if not self.bill_number:
            while True:
                cap_letters = ''.join(random.choices(string.ascii_uppercase, k=3))
                six_digits = str(random.randint(100000, 999999))
                cand = f"JEB-{cap_letters}{six_digits}"
                if not Bill.objects.filter(bill_number=cand).exists():
                    self.bill_number = cand
                    break

        self.payment_status = self.calculate_payment_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Bill #{self.bill_number} - {self.customer_name} (Total: ₹{self.grand_total}, Paid: ₹{self.paid_amount})"

    @property
    def paid_percentage(self):
        if not self.grand_total or self.grand_total == 0:
            return 100.0
        return round(min(100.0, (float(self.paid_amount) / float(self.grand_total)) * 100), 1)

    @property
    def gender_icon(self):
        icons = {'MALE': '👨', 'FEMALE': '👩', 'OTHER': '⚧'}
        return icons.get(self.gender, '👤')

    @property
    def id_proof_label(self):
        labels = dict(self.ID_PROOF_CHOICES)
        return labels.get(self.id_proof_type, 'ID Proof')


class BillItem(models.Model):
    """
    Individual product line item in a Bill.
    Snapshots product information and calculates line total.
    """
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    category_name = models.CharField(max_length=120, blank=True, default='')
    size = models.CharField(max_length=80)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.00, verbose_name="Quantity / Meters")
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Bill Item"
        verbose_name_plural = "Bill Items"

    def __str__(self):
        return f"{self.product_name} ({self.size}) x {self.quantity} = ₹{self.total}"

    def save(self, *args, **kwargs):
        if self.rate is not None and self.quantity is not None:
            self.total = round(float(self.rate) * float(self.quantity), 2)
        else:
            self.total = 0.00
        super().save(*args, **kwargs)

    @property
    def is_pipe(self):
        """Identifies if this line item is a plumbing pipe (sold by meters & standard 6m lengths)"""
        if self.product:
            if self.product.unit == 'METER':
                return True
            if self.product.unit == 'PIECE':
                return False

        pname = self.product_name.lower()
        cname = self.category_name.lower()
        fitting_keywords = [
            'elbow', 'tee', 'reducer', 'coupler', 'coupling', 'socket', 'union', 
            'nipple', 'valve', 'cock', 'tap', 'faucet', 'clamp', 'bush', 'bushing', 
            'plug', 'cap', 'bend', 'trap', 'collar', 'fitting', 'flange', 'adapter', 
            'solvent', 'cement', 'tape', 'glue', 'clip', 'shower', 'waste', 'bracket',
            'screw', 'tools', 'sealant', 'ball valve', 'bib tap', 'angle valve'
        ]
        if any(kw in pname for kw in fitting_keywords):
            return False
        if any(kw in cname for kw in ['valve', 'tap', 'hardware', 'tool', 'sealant']):
            return False

        if 'pipe' in cname and 'fitting' not in cname:
            return True
        return 'pipe' in pname

    @property
    def pipe_std_len(self):
        """Standard full length of pipe in meters (Default: 6.00 meters = approx 20 feet)"""
        if self.product and self.product.pipe_length:
            return float(self.product.pipe_length)
        return 6.00

    @property
    def pipe_lengths(self):
        """Calculate how many full pipe lengths were purchased (1 Length = 6m)"""
        std = self.pipe_std_len
        qty = float(self.quantity or 0)
        lens = qty / std if std > 0 else qty
        return int(lens) if lens.is_integer() else round(lens, 2)

    @property
    def pipe_meters(self):
        """Total meters of pipe"""
        return float(self.quantity or 0)

    @property
    def pipe_feet(self):
        """Approximate feet of pipe (1 Length = 20 Feet, 1 meter = 3.28084 feet)"""
        std = self.pipe_std_len
        if std == 6.00:
            return int(round(float(self.pipe_lengths) * 20))
        return int(round(self.pipe_meters * 3.28084))

    @property
    def pipe_display(self):
        """Display breakdown: e.g., '2 Lengths = 12.00 Meters (40 Feet)'"""
        if not self.is_pipe:
            return ""
        lens = self.pipe_lengths
        meters = self.pipe_meters
        feet = self.pipe_feet
        return f"{lens} Length{'s' if lens != 1 else ''} = {meters:.2f} Meters ({feet} Feet)"


class Supplier(models.Model):
    """
    Suppliers and wholesale distributors providing plumbing and hardware materials to ZAM ZAM HARDWARE (Owner: Lawrence C).
    """
    name = models.CharField(max_length=150, help_text="Supplier contact person name")
    company_name = models.CharField(max_length=200, help_text="Business / Agency / Brand name (e.g., Supreme Industries, Ashirvad Pipes)")
    phone = models.CharField(max_length=25, help_text="Mobile or phone number")
    email = models.EmailField(blank=True, null=True, help_text="Email address")
    address = models.TextField(blank=True, null=True, help_text="Warehouse / Office address")
    gstin = models.CharField(max_length=30, blank=True, null=True, verbose_name="GSTIN No")
    supply_category = models.CharField(max_length=150, blank=True, default="Pipes & Fittings", help_text="Main materials supplied")
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Balance Due to Supplier")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Supplier / Vendor"
        verbose_name_plural = "Suppliers & Vendors"
        ordering = ['company_name', 'name']

    def __str__(self):
        return f"{self.company_name} ({self.name})"


class Expense(models.Model):
    """
    Store operating expenses (Rent, Electricity, Freight, Staff Wages, Maintenance, Tea/Snacks).
    Used for Net Profit computation on Admin Dashboard.
    """
    EXPENSE_CATEGORIES = [
        ('RENT', 'Shop Rent'),
        ('ELECTRICITY', 'Electricity & Utilities'),
        ('SALARY', 'Staff Wages & Salaries'),
        ('FREIGHT', 'Freight & Transportation'),
        ('SUPPLIES', 'Shop Consumables & Packing'),
        ('MAINTENANCE', 'Repairs & Maintenance'),
        ('TEA_SNACKS', 'Tea & Refreshments'),
        ('OTHER', 'General / Other'),
    ]

    PAYMENT_MODES = [
        ('CASH', 'Cash'),
        ('UPI', 'UPI / GPay / PhonePe'),
        ('BANK', 'Net Banking / NEFT'),
        ('CARD', 'Debit / Credit Card'),
    ]

    title = models.CharField(max_length=200, help_text="Expense description (e.g., October Shop Rent, Freight Delivery)")
    category = models.CharField(max_length=30, choices=EXPENSE_CATEGORIES, default='OTHER')
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount paid in ₹")
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='CASH')
    expense_date = models.DateField(default=timezone.now, help_text="Date of expenditure")
    reference_no = models.CharField(max_length=80, blank=True, null=True, help_text="Receipt, voucher or reference ID")
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Shop Expense"
        verbose_name_plural = "Shop Expenses"
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.title} - ₹{self.amount} ({self.get_category_display()})"


class FeaturedOfferProduct(models.Model):
    """
    Featured Product Offer Cards shown on the homepage (index.html) single-row 4-card showcase.
    Managed exclusively by Admin in Django Admin and Executive Admin Dashboard.
    Contains image, product name, size, category, original price, discount price, offer date, and button.
    """
    name = models.CharField(max_length=200, help_text="Product offer title (e.g., CPVC High-Pressure Concealed Valve)")
    category_name = models.CharField(max_length=120, default="Valves & Fittings", help_text="Category badge text")
    size = models.CharField(max_length=80, default="3/4 inch (20mm)", help_text="Size/dimension (e.g., 3/4 inch (20mm))")
    image_url = models.URLField(
        max_length=500,
        default="https://images.unsplash.com/photo-1585704032915-c3400ca199e7?auto=format&fit=crop&w=600&q=80",
        help_text="Product image URL (e.g., Unsplash or direct image link)"
    )
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Original standard price / MRP in ₹"
    )
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Discounted offer price in ₹"
    )
    offer_date = models.CharField(
        max_length=100, default="30 Nov 2026",
        help_text="Offer validity deadline (e.g., 30 Nov 2026, Limited Time)"
    )
    description = models.TextField(
        blank=True, default="",
        help_text="Brief highlight / specifications for card display"
    )
    button_text = models.CharField(max_length=80, default="🛒 Add to Bill / Enquire")
    button_link = models.CharField(max_length=200, default="/pos/", help_text="Link destination when button is clicked")
    order = models.PositiveIntegerField(default=1, help_text="Display order sequence (1 to 4)")
    is_active = models.BooleanField(default=True, help_text="Show this offer card on homepage")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Featured Offer Product (Homepage)"
        verbose_name_plural = "Featured Offer Products (Homepage)"
        ordering = ['order', '-created_at']

    def clean(self):
        super().clean()
        if self.name and self.size:
            n = self.name.strip()
            s = self.size.strip()
            qs = FeaturedOfferProduct.objects.filter(name__iexact=n, size__iexact=s)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'name': f'This featured offer product "{n} ({s})" is already added! Duplicate offer cards are not allowed.'
                })

    def __str__(self):
        return f"{self.name} ({self.size}) - ₹{self.discount_price} (Offer: {self.offer_date})"

    @property
    def discount_percent(self):
        try:
            orig = float(self.original_price or 0)
            disc = float(self.discount_price or 0)
            if orig > disc and orig > 0:
                pct = round(((orig - disc) / orig) * 100)
                return f"{pct}% OFF"
        except Exception:
            pass
        return "SPECIAL OFFER"


