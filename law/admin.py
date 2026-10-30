from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, Bill, BillItem, Supplier, Expense, FeaturedOfferProduct

# Customize Django Admin Header and Branding for Shop Owner Lawrence C
admin.site.site_header = "ZAM ZAM HARDWARE - Administration"
admin.site.site_title = "ZAM ZAM HARDWARE Admin"
admin.site.index_title = "Shop Owner: Lawrence C | Billing & Inventory Control Panel"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'get_product_count', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)

    @admin.display(description="Total Products")
    def get_product_count(self, obj):
        count = obj.products.count()
        return format_html('<span style="font-weight: bold; color: #2563eb;">{} items</span>', count)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'size', 'formatted_rate', 'quantity', 'stock_value', 'stock_status')
    list_filter = ('category', 'size')
    search_fields = ('name', 'size', 'category__name')
    list_per_page = 25
    readonly_fields = ('stock_value', 'created_at', 'updated_at')

    fieldsets = (
        ("Product Information", {
            'fields': ('category', 'name', 'size')
        }),
        ("Pricing & Inventory", {
            'fields': ('rate', 'quantity', 'stock_value')
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description="Rate / Unit", ordering='rate')
    def formatted_rate(self, obj):
        if not obj or obj.rate is None:
            return "₹0.00"
        return f"₹{obj.rate:.2f}"

    @admin.display(description="Total Stock Value", ordering='rate')
    def stock_value(self, obj):
        if not obj or obj.total is None:
            return format_html('<strong>₹0.00</strong>')
        formatted = f"₹{float(obj.total):,.2f}"
        return format_html('<strong>{}</strong>', formatted)

    @admin.display(description="Inventory Status")
    def stock_status(self, obj):
        if not obj or obj.quantity is None:
            return "-"
        if obj.quantity == 0:
            return format_html(
                '<span style="background-color: #fee2e2; color: #b91c1c; padding: 3px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">{}</span>',
                "Out of Stock"
            )
        elif obj.quantity <= 10:
            return format_html(
                '<span style="background-color: #fef3c7; color: #b45309; padding: 3px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">Low Stock ({})</span>',
                obj.quantity
            )
        else:
            return format_html(
                '<span style="background-color: #dcfce7; color: #15803d; padding: 3px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">In Stock ({})</span>',
                obj.quantity
            )


class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 0
    readonly_fields = ('total',)
    fields = ('product', 'product_name', 'category_name', 'size', 'rate', 'quantity', 'total')


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        'bill_number', 'customer_with_gender', 'customer_phone', 'id_proof_summary',
        'formatted_total', 'formatted_paid', 'formatted_balance', 'payment_status_badge',
        'payment_badge', 'created_at'
    )
    list_filter = ('payment_status', 'payment_mode', 'gender', 'id_proof_type', 'created_at')
    search_fields = ('bill_number', 'customer_name', 'customer_phone', 'door_no', 'address', 'id_proof_number')
    readonly_fields = ('bill_number', 'created_at', 'balance_amount', 'payment_status')
    inlines = [BillItemInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ("Invoice Meta", {
            'fields': ('bill_number', 'created_at')
        }),
        ("Customer Information & ID Proof", {
            'fields': (
                ('customer_name', 'gender'),
                ('customer_phone', 'door_no'),
                'address',
                ('id_proof_type', 'id_proof_number')
            )
        }),
        ("Billing & Tax Calculation", {
            'fields': (
                ('subtotal', 'discount'),
                ('gst_rate', 'gst_amount'),
                'grand_total'
            )
        }),
        ("Payment Details & Status", {
            'fields': (
                ('paid_amount', 'balance_amount'),
                ('payment_status', 'payment_mode'),
                'notes'
            )
        }),
    )

    @admin.display(description="Customer")
    def customer_with_gender(self, obj):
        if not obj:
            return "-"
        icon = obj.gender_icon
        return format_html('<span>{} <strong>{}</strong></span>', icon, obj.customer_name)

    @admin.display(description="ID Proof")
    def id_proof_summary(self, obj):
        if not obj or not obj.id_proof_number:
            return format_html('<span style="color: #94a3b8;">None</span>')
        return format_html('<span style="font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-weight: 600;">{}: {}</span>', obj.get_id_proof_type_display(), obj.id_proof_number)

    @admin.display(description="Grand Total", ordering='grand_total')
    def formatted_total(self, obj):
        if not obj or obj.grand_total is None:
            return "₹0.00"
        formatted = f"₹{float(obj.grand_total):,.2f}"
        return format_html('<span style="font-weight: 700; color: #0f172a;">{}</span>', formatted)

    @admin.display(description="Paid Amount", ordering='paid_amount')
    def formatted_paid(self, obj):
        if not obj or obj.paid_amount is None:
            return "₹0.00"
        formatted = f"₹{float(obj.paid_amount):,.2f}"
        return format_html('<span style="font-weight: 600; color: #16a34a;">{}</span>', formatted)

    @admin.display(description="Balance Due", ordering='balance_amount')
    def formatted_balance(self, obj):
        if not obj or obj.balance_amount is None:
            return "₹0.00"
        bal = float(obj.balance_amount)
        formatted = f"₹{bal:,.2f}"
        color = "#dc2626" if bal > 0 else "#16a34a"
        return format_html('<span style="font-weight: 700; color: {};">{}</span>', color, formatted)

    @admin.display(description="Payment Status")
    def payment_status_badge(self, obj):
        if not obj or not obj.payment_status:
            return "-"
        style_map = {
            'COMPLETED_PAID': ('#dcfce7', '#15803d', 'Completed Paid'),
            'HIGH_80_PAID': ('#e0f2fe', '#0369a1', '80%+ High Paid'),
            'HIGH_50_PAID': ('#fef3c7', '#b45309', '50%+ High Paid'),
            'DOWN_50_PAID': ('#ffedd5', '#c2410c', '50% Down Paid'),
            'NO_PAID': ('#fee2e2', '#b91c1c', 'No Paid'),
        }
        bg, text_color, label = style_map.get(obj.payment_status, ('#f1f5f9', '#475569', obj.payment_status))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 3px 8px; border-radius: 9999px; font-weight: 700; font-size: 11px;">{}</span>',
            bg, text_color, label
        )

    @admin.display(description="Payment Mode")
    def payment_badge(self, obj):
        if not obj or not obj.payment_mode:
            return "-"
        color_map = {
            'CASH': '#16a34a',
            'UPI': '#2563eb',
            'CARD': '#9333ea',
            'CREDIT': '#ea580c',
        }
        color = color_map.get(obj.payment_mode, '#475569')
        return format_html('<span style="color: {}; font-weight: 600;">{}</span>', color, obj.get_payment_mode_display())


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'name', 'phone', 'supply_category', 'formatted_due', 'gstin', 'created_at')
    search_fields = ('company_name', 'name', 'phone', 'gstin')
    list_filter = ('supply_category', 'created_at')
    ordering = ('company_name',)

    @admin.display(description="Balance Due", ordering='balance_due')
    def formatted_due(self, obj):
        bal = float(obj.balance_due or 0)
        formatted = f"₹{bal:,.2f}"
        color = "#dc2626" if bal > 0 else "#16a34a"
        return format_html('<span style="font-weight: 700; color: {};">{}</span>', color, formatted)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category_badge', 'formatted_amount', 'payment_mode', 'expense_date', 'reference_no')
    list_filter = ('category', 'payment_mode', 'expense_date')
    search_fields = ('title', 'reference_no', 'notes')
    date_hierarchy = 'expense_date'
    ordering = ('-expense_date',)

    @admin.display(description="Category")
    def category_badge(self, obj):
        return format_html(
            '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 9999px; font-weight: 700; font-size: 11px;">{}</span>',
            obj.get_category_display()
        )

    @admin.display(description="Amount", ordering='amount')
    def formatted_amount(self, obj):
        amt = float(obj.amount or 0)
        formatted = f"₹{amt:,.2f}"
        return format_html('<span style="font-weight: 800; color: #dc2626;">{}</span>', formatted)


@admin.register(FeaturedOfferProduct)
class FeaturedOfferProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category_name', 'size', 'formatted_discount_price',
        'formatted_original_price', 'discount_badge', 'offer_date',
        'order', 'is_active', 'image_preview'
    )
    list_filter = ('is_active', 'category_name', 'offer_date')
    search_fields = ('name', 'size', 'category_name', 'description')
    list_editable = ('order', 'is_active')
    ordering = ('order', '-created_at')

    fieldsets = (
        ("Offer Product Details", {
            'fields': (
                ('name', 'category_name'),
                ('size', 'image_url'),
                'description',
            )
        }),
        ("Offer Pricing & Deadline", {
            'fields': (
                ('original_price', 'discount_price'),
                ('offer_date', 'button_text', 'button_link'),
            )
        }),
        ("Visibility & Sorting", {
            'fields': (
                ('order', 'is_active'),
            )
        }),
    )

    @admin.display(description="Offer Price", ordering='discount_price')
    def formatted_discount_price(self, obj):
        amt = float(obj.discount_price or 0)
        formatted = f"₹{amt:,.2f}"
        return format_html('<span style="font-weight: 800; color: #0284c7;">{}</span>', formatted)

    @admin.display(description="Original MRP", ordering='original_price')
    def formatted_original_price(self, obj):
        amt = float(obj.original_price or 0)
        formatted = f"₹{amt:,.2f}"
        return format_html('<span style="text-decoration: line-through; color: #94a3b8;">{}</span>', formatted)

    @admin.display(description="Discount Badge")
    def discount_badge(self, obj):
        return format_html(
            '<span style="background: #fee2e2; color: #dc2626; padding: 2px 8px; border-radius: 6px; font-weight: 800; font-size: 11px;">{}</span>',
            obj.discount_percent
        )

    @admin.display(description="Image Preview")
    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="width: 44px; height: 32px; object-fit: cover; border-radius: 4px; border: 1px solid #cbd5e1;" />', obj.image_url)
        return "-"




