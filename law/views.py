import json
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from .models import Category, Product, Bill, BillItem, Supplier, Expense, FeaturedOfferProduct


def index_view(request):
    """
    Public Homepage / Landing Page for ZAM ZAM HARDWARE (Owner: Lawrence C).
    Features Fullscreen Hero, About Shop, 4-Card Single-Row Product Offers (Admin Managed),
    3-Card Plumbing Services, and Contact section with Google Maps.
    """
    # Fetch dynamic featured offer products managed by Admin in backend
    db_featured = FeaturedOfferProduct.objects.filter(is_active=True).order_by('order', '-created_at')[:4]
    
    if db_featured.exists():
        featured_products = []
        for f in db_featured:
            featured_products.append({
                'id': f.id,
                'name': f.name,
                'category': f.category_name,
                'size': f.size,
                'image': f.image_url,
                'original_price': float(f.original_price),
                'discount_price': float(f.discount_price),
                'discount_percent': f.discount_percent,
                'offer_date': f.offer_date,
                'description': f.description,
                'button_text': f.button_text,
                'button_link': f.button_link,
            })
    else:
        featured_products = [
            {
                'name': 'CPVC High-Pressure Concealed Valve',
                'category': 'Valves & Fittings',
                'size': '3/4 inch (20mm)',
                'image': 'https://images.unsplash.com/photo-1585704032915-c3400ca199e7?auto=format&fit=crop&w=600&q=80',
                'original_price': 480.00,
                'discount_price': 349.00,
                'discount_percent': '27% OFF',
                'offer_date': '30 Nov 2026',
                'description': 'Heavy-duty brass ball valve engineered for leak-free, corrosion-resistant hot and cold water control.',
                'button_text': '🛒 Add to Bill / Enquire',
                'button_link': '/pos/',
            },
            {
                'name': 'Premium Brass Long Body Bib Cock',
                'category': 'Taps & Faucets',
                'size': '1/2 inch Standard',
                'image': 'https://images.unsplash.com/photo-1584622650111-993a426fbf0a?auto=format&fit=crop&w=600&q=80',
                'original_price': 390.00,
                'discount_price': 275.00,
                'discount_percent': '30% OFF',
                'offer_date': '30 Nov 2026',
                'description': 'High-gloss chrome finish brass bib tap for washbasin, kitchen sink, and garden water outlets.',
                'button_text': '🛒 Add to Bill / Enquire',
                'button_link': '/pos/',
            },
            {
                'name': 'Rigid PVC Pressure Pipe & Elbow Set',
                'category': 'Pipes & Fittings',
                'size': '1 inch (25mm) / 4m',
                'image': 'https://images.unsplash.com/photo-1607472586893-edb57bdc0e39?auto=format&fit=crop&w=600&q=80',
                'original_price': 260.00,
                'discount_price': 189.00,
                'discount_percent': '27% OFF',
                'offer_date': '30 Nov 2026',
                'description': 'Heavy schedule rigid PVC pipes with seamless 90-degree elbows for high-pressure water transmission.',
                'button_text': '🛒 Add to Bill / Enquire',
                'button_link': '/pos/',
            },
            {
                'name': 'SS Overhead Rain Shower & Wall Arm',
                'category': 'Showers & Sanitary',
                'size': '6x6 inch Round',
                'image': 'https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?auto=format&fit=crop&w=600&q=80',
                'original_price': 750.00,
                'discount_price': 520.00,
                'discount_percent': '31% OFF',
                'offer_date': '30 Nov 2026',
                'description': 'Anti-clog silicone nozzles with 304 grade stainless steel arm for luxurious rainfall water spray.',
                'button_text': '🛒 Add to Bill / Enquire',
                'button_link': '/pos/',
            },
        ]

    categories = Category.objects.prefetch_related('products').all()
    products = Product.objects.select_related('category').all()

    context = {
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'shop_phone': "+91 98765 43210",
        'shop_phone_alt': "+91 98401 23456",
        'shop_email': "contact@zamzamhardware.com",
        'shop_address': "Main Road, Near Old Bus Stand, Hardware Market, Chennai, Tamil Nadu - 600001",
        'featured_products': featured_products,
        'categories': categories,
        'products': products,
    }
    return render(request, 'law/index.html', context)


def billing_pos(request):
    """
    Main Point-of-Sale (POS) and Billing Terminal for ZAM ZAM HARDWARE.
    """
    categories = Category.objects.prefetch_related('products').all()
    products = Product.objects.select_related('category').all()
    recent_bills = Bill.objects.prefetch_related('items').all()[:8]
    total_sales = sum(b.grand_total for b in Bill.objects.all())
    total_invoices = Bill.objects.count()
    low_stock_count = Product.objects.filter(quantity__lte=10).count()

    context = {
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'shop_phone': "+91 98765 43210",
        'shop_address': "Main Road, Near Old Bus Stand, Hardware Market",
        'categories': categories,
        'products': products,
        'recent_bills': recent_bills,
        'total_sales': total_sales,
        'total_invoices': total_invoices,
        'low_stock_count': low_stock_count,
        'product_count': products.count(),
    }
    return render(request, 'law/billing_pos.html', context)


def inventory_view(request):
    """
    Inventory management view with live stock, rates, sizes, and total values for ZAM ZAM HARDWARE.
    """
    categories = Category.objects.all()
    products = Product.objects.select_related('category').all()
    total_inventory_value = sum(p.total for p in products)
    low_stock_count = products.filter(quantity__lte=10).count()

    context = {
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'categories': categories,
        'products': products,
        'total_inventory_value': total_inventory_value,
        'total_items_count': products.count(),
        'low_stock_count': low_stock_count,
    }
    return render(request, 'law/inventory.html', context)


def invoices_list(request):
    """
    List of all historical bills and invoices with stats and category-wise product selection.
    """
    bills = Bill.objects.prefetch_related('items').all()
    products = Product.objects.select_related('category').all()
    categories = Category.objects.prefetch_related('products').all()

    total_revenue = sum(b.grand_total for b in bills)
    total_paid = sum(b.paid_amount for b in bills)
    total_balance = sum(b.balance_amount for b in bills)

    completed_paid_count = bills.filter(payment_status='COMPLETED_PAID').count()
    high_80_count = bills.filter(payment_status='HIGH_80_PAID').count()
    high_50_count = bills.filter(payment_status='HIGH_50_PAID').count()
    down_50_count = bills.filter(payment_status='DOWN_50_PAID').count()
    no_paid_count = bills.filter(payment_status='NO_PAID').count()

    context = {
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'bills': bills,
        'products': products,
        'categories': categories,
        'total_bills_count': bills.count(),
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'completed_paid_count': completed_paid_count,
        'high_80_count': high_80_count,
        'high_50_count': high_50_count,
        'down_50_count': down_50_count,
        'no_paid_count': no_paid_count,
    }
    return render(request, 'law/invoices_list.html', context)


def invoice_detail(request, bill_id):
    """
    Printable and downloadable tax invoice receipt for customer.
    """
    bill = get_object_or_404(Bill.objects.prefetch_related('items'), id=bill_id)
    context = {
        'bill': bill,
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'shop_phone': "+91 98765 43210",
        'shop_address': "Main Road, Near Old Bus Stand, Hardware Market",
        'gstin': "33AAACJ1234F1Z8",
    }
    return render(request, 'law/invoice_print.html', context)


@csrf_exempt
def create_bill_api(request):
    """
    JSON API endpoint to record a new bill, snapshot items, and automatically deduct stock.
    Supports customer name, mobile, gender, door no, address, ID proof, GST, paid amount & balance.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)

    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        if not items:
            return JsonResponse({'status': 'error', 'message': 'No items added in the bill'}, status=400)

        customer_name = (data.get('customer_name') or '').strip() or 'Walk-in Customer'
        customer_phone = (data.get('customer_phone') or '').strip()
        gender = data.get('gender', 'MALE')
        if gender not in ['MALE', 'FEMALE', 'OTHER']:
            gender = 'MALE'

        door_no = (data.get('door_no') or '').strip()
        address = (data.get('address') or '').strip()
        id_proof_type = data.get('id_proof_type', 'AADHAAR')
        id_proof_number = (data.get('id_proof_number') or '').strip()
        payment_mode = data.get('payment_mode', 'CASH')
        notes = (data.get('notes') or '').strip()

        discount = float(data.get('discount', 0) or 0)
        gst_rate = float(data.get('gst_rate', 18) if data.get('gst_rate') is not None else 18)
        paid_amount_input = data.get('paid_amount')

        with transaction.atomic():
            subtotal = 0.0
            bill_items_to_create = []

            for item in items:
                product_id = item.get('product_id')
                qty = int(item.get('quantity', 1))
                if qty <= 0:
                    continue

                prod = get_object_or_404(Product, id=product_id)
                rate = float(prod.rate)
                line_total = round(rate * qty, 2)
                subtotal += line_total

                # Deduct stock safely
                if prod.quantity >= qty:
                    prod.quantity -= qty
                else:
                    prod.quantity = 0
                prod.save(update_fields=['quantity', 'updated_at'])

                bill_items_to_create.append({
                    'product': prod,
                    'product_name': prod.name,
                    'category_name': prod.category.name,
                    'size': prod.size,
                    'rate': rate,
                    'quantity': qty,
                    'total': line_total,
                })

            subtotal = round(subtotal, 2)
            taxable_amount = max(0.0, round(subtotal - discount, 2))
            gst_amount = round((taxable_amount * gst_rate) / 100.0, 2)
            grand_total = round(taxable_amount + gst_amount, 2)

            if paid_amount_input is None or str(paid_amount_input).strip() == '':
                # Default to full paid if not specified
                paid_amount = grand_total
            else:
                paid_amount = float(paid_amount_input or 0)

            balance_amount = max(0.0, round(grand_total - paid_amount, 2))

            bill = Bill.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                gender=gender,
                door_no=door_no,
                address=address,
                id_proof_type=id_proof_type,
                id_proof_number=id_proof_number,
                payment_mode=payment_mode,
                subtotal=subtotal,
                discount=discount,
                gst_rate=gst_rate,
                gst_amount=gst_amount,
                grand_total=grand_total,
                paid_amount=paid_amount,
                balance_amount=balance_amount,
                notes=notes
            )

            for b_item in bill_items_to_create:
                BillItem.objects.create(
                    bill=bill,
                    product=b_item['product'],
                    product_name=b_item['product_name'],
                    category_name=b_item['category_name'],
                    size=b_item['size'],
                    rate=b_item['rate'],
                    quantity=b_item['quantity'],
                    total=b_item['total'],
                )

            return JsonResponse({
                'status': 'success',
                'bill_id': bill.id,
                'bill_number': bill.bill_number,
                'customer_name': bill.customer_name,
                'subtotal': float(bill.subtotal),
                'discount': float(bill.discount),
                'gst_rate': float(bill.gst_rate),
                'gst_amount': float(bill.gst_amount),
                'grand_total': float(bill.grand_total),
                'paid_amount': float(bill.paid_amount),
                'balance_amount': float(bill.balance_amount),
                'payment_status': bill.payment_status,
                'payment_status_display': bill.get_payment_status_display(),
                'created_at': bill.created_at.strftime('%d-%b-%Y %I:%M %p')
            })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



@csrf_exempt
def add_product_api(request):
    """API to add a new product directly from the web interface."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        cat_id = data.get('category_id')
        name = (data.get('name') or '').strip()
        size = (data.get('size') or '').strip()
        rate = float(data.get('rate', 0))
        quantity = int(data.get('quantity', 0))

        if not name or not size:
            return JsonResponse({'status': 'error', 'message': 'Product name and size are required.'}, status=400)

        category = get_object_or_404(Category, id=cat_id)

        # Check for duplicate product under this category
        if Product.objects.filter(category=category, name__iexact=name, size__iexact=size).exists():
            return JsonResponse({
                'status': 'error',
                'is_duplicate': True,
                'message': f'This item "{name} ({size})" is already added in category "{category.name}"! Duplicate product is not allowed.'
            }, status=400)

        prod = Product.objects.create(
            category=category,
            name=name,
            size=size,
            rate=rate,
            quantity=max(0, quantity)
        )
        return JsonResponse({
            'status': 'success',
            'message': f'Product "{prod.name}" added successfully!',
            'product_id': prod.id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def edit_product_api(request, product_id):
    """API to edit an existing product."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        prod = get_object_or_404(Product, id=product_id)

        new_category = prod.category
        if 'category_id' in data and data['category_id']:
            new_category = get_object_or_404(Category, id=data['category_id'])
        new_name = str(data.get('name', prod.name)).strip()
        new_size = str(data.get('size', prod.size)).strip()

        # Check for duplicate product when editing
        if Product.objects.filter(category=new_category, name__iexact=new_name, size__iexact=new_size).exclude(id=prod.id).exists():
            return JsonResponse({
                'status': 'error',
                'is_duplicate': True,
                'message': f'This item "{new_name} ({new_size})" is already added in category "{new_category.name}"! Duplicate product is not allowed.'
            }, status=400)

        prod.category = new_category
        prod.name = new_name
        prod.size = new_size
        if 'rate' in data:
            prod.rate = float(data['rate'])
        if 'quantity' in data:
            prod.quantity = max(0, int(data['quantity']))

        prod.save()
        return JsonResponse({
            'status': 'success',
            'message': f'Product "{prod.name}" updated successfully!',
            'product_id': prod.id,
            'rate': float(prod.rate),
            'quantity': prod.quantity,
            'total': float(prod.total)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_product_api(request, product_id):
    """API to delete a single product."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        prod = get_object_or_404(Product, id=product_id)
        name = prod.name
        prod.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Product "{name}" deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def bulk_delete_products_api(request):
    """API to delete multiple selected products at once."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        ids = data.get('product_ids', [])
        if not ids:
            return JsonResponse({'status': 'error', 'message': 'No products selected for deletion.'}, status=400)

        count = Product.objects.filter(id__in=ids).count()
        Product.objects.filter(id__in=ids).delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully deleted {count} selected product(s)!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def edit_invoice_api(request, bill_id):
    """API to edit customer details, ID proof, payment mode, or paid amount on an existing invoice."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        bill = get_object_or_404(Bill, id=bill_id)

        if 'customer_name' in data and str(data['customer_name']).strip():
            bill.customer_name = str(data['customer_name']).strip()
        if 'customer_phone' in data:
            bill.customer_phone = str(data['customer_phone']).strip()
        if 'gender' in data and data['gender'] in ['MALE', 'FEMALE', 'OTHER']:
            bill.gender = data['gender']
        if 'door_no' in data:
            bill.door_no = str(data['door_no']).strip()
        if 'address' in data:
            bill.address = str(data['address']).strip()
        if 'id_proof_type' in data and data['id_proof_type']:
            bill.id_proof_type = data['id_proof_type']
        if 'id_proof_number' in data:
            bill.id_proof_number = str(data['id_proof_number']).strip()
        if 'payment_mode' in data and data['payment_mode']:
            bill.payment_mode = data['payment_mode']
        if 'paid_amount' in data and data['paid_amount'] is not None:
            bill.paid_amount = max(0.0, float(data['paid_amount']))
            bill.balance_amount = max(0.0, round(float(bill.grand_total) - float(bill.paid_amount), 2))
        if 'notes' in data:
            bill.notes = str(data['notes']).strip()

        bill.payment_status = bill.calculate_payment_status()
        bill.save()

        return JsonResponse({
            'status': 'success',
            'message': f'Invoice #{bill.bill_number} updated successfully!',
            'bill_id': bill.id,
            'customer_name': bill.customer_name,
            'paid_amount': float(bill.paid_amount),
            'balance_amount': float(bill.balance_amount),
            'payment_status': bill.payment_status,
            'payment_status_display': bill.get_payment_status_display()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



@csrf_exempt
def delete_invoice_api(request, bill_id):
    """API to delete a single invoice."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        bill = get_object_or_404(Bill, id=bill_id)
        bill_num = bill.bill_number
        bill.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Invoice #{bill_num} deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def bulk_delete_invoices_api(request):
    """API to delete multiple selected invoices at once."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        ids = data.get('bill_ids', [])
        if not ids:
            return JsonResponse({'status': 'error', 'message': 'No invoices selected for deletion.'}, status=400)

        count = Bill.objects.filter(id__in=ids).count()
        Bill.objects.filter(id__in=ids).delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully deleted {count} selected invoice(s)!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def admin_dashboard(request):
    """
    Comprehensive Executive Admin Dashboard for ZAM ZAM HARDWARE (Owner: Lawrence C).
    Shows key business analytics, stock alerts, financial overview, categories,
    quick creation modals, recent bills, expenses, and supplier status.
    """
    products = Product.objects.select_related('category').all()
    categories = Category.objects.prefetch_related('products').all()
    bills = Bill.objects.prefetch_related('items').all()
    expenses = Expense.objects.all()[:20]
    suppliers = Supplier.objects.all()

    today = timezone.now().date()
    
    # 1. Total Stock Count by Product
    total_products_count = products.count()
    low_stock_products = [p for p in products if p.quantity is not None and p.quantity <= 10]
    out_of_stock_products = [p for p in products if p.quantity is not None and p.quantity == 0]
    low_stock_count = len(low_stock_products)
    out_of_stock_count = len(out_of_stock_products)

    # 4. Total Stock Price Amount (Asset Valuation)
    total_inventory_value = sum(float(p.total or 0) for p in products)
    total_stock_units = sum(int(p.quantity or 0) for p in products)

    # 5. Daily Amount (Today's Sales)
    daily_bills = [b for b in bills if b.created_at.date() == today]
    daily_sales = sum(float(b.grand_total or 0) for b in daily_bills)
    daily_invoices_count = len(daily_bills)

    # 6. Weekly Amount (Current Week: Monday to Today)
    start_of_week = today - timedelta(days=today.weekday())
    weekly_bills = [b for b in bills if b.created_at.date() >= start_of_week]
    weekly_sales = sum(float(b.grand_total or 0) for b in weekly_bills)
    weekly_invoices_count = len(weekly_bills)

    # 7. Monthly Amount (Current Month)
    monthly_bills = [b for b in bills if b.created_at.year == today.year and b.created_at.month == today.month]
    monthly_sales = sum(float(b.grand_total or 0) for b in monthly_bills)
    monthly_invoices_count = len(monthly_bills)

    # 8. Yearly Amount (Current Year)
    yearly_bills = [b for b in bills if b.created_at.year == today.year]
    yearly_sales = sum(float(b.grand_total or 0) for b in yearly_bills)
    yearly_invoices_count = len(yearly_bills)

    # 9. Full Total Amount (All-Time Revenue)
    total_revenue = sum(float(b.grand_total or 0) for b in bills)
    total_paid = sum(float(b.paid_amount or 0) for b in bills)
    total_balance = sum(float(b.balance_amount or 0) for b in bills)
    total_invoices = bills.count()

    all_expenses = Expense.objects.all()
    total_expenses = sum(float(e.amount or 0) for e in all_expenses)
    net_profit = total_revenue - total_expenses
    total_supplier_dues = sum(float(s.balance_due or 0) for s in suppliers)

    # 10. Separate Cash & Net Banking / Online Model Payments
    cash_total = sum(float(b.grand_total or 0) for b in bills if b.payment_mode == 'CASH')
    upi_total = sum(float(b.grand_total or 0) for b in bills if b.payment_mode == 'UPI')
    card_total = sum(float(b.grand_total or 0) for b in bills if b.payment_mode == 'CARD')
    credit_total = sum(float(b.grand_total or 0) for b in bills if b.payment_mode == 'CREDIT')
    net_banking_online_total = upi_total + card_total

    # 11. Offers Card Show Count
    featured_offers = FeaturedOfferProduct.objects.all().order_by('order', '-created_at')
    featured_offers_count = featured_offers.filter(is_active=True).count()

    # 12. Calendar Sales Data Map (date -> count, total) for Interactive Full Calendar
    calendar_sales_data = {}
    for b in bills:
        d_str = b.created_at.date().isoformat()
        if d_str not in calendar_sales_data:
            calendar_sales_data[d_str] = {'count': 0, 'total': 0.0}
        calendar_sales_data[d_str]['count'] += 1
        calendar_sales_data[d_str]['total'] += float(b.grand_total or 0)
    calendar_sales_json = json.dumps(calendar_sales_data)

    # Payment status counts
    completed_paid_count = bills.filter(payment_status='COMPLETED_PAID').count()
    high_80_count = bills.filter(payment_status='HIGH_80_PAID').count()
    high_50_count = bills.filter(payment_status='HIGH_50_PAID').count()
    down_50_count = bills.filter(payment_status='DOWN_50_PAID').count()
    no_paid_count = bills.filter(payment_status='NO_PAID').count()

    # Category analytics
    category_analytics = []
    for cat in categories:
        cat_prods = cat.products.all()
        cat_val = sum(float(p.total or 0) for p in cat_prods)
        cat_units = sum(int(p.quantity or 0) for p in cat_prods)
        category_analytics.append({
            'id': cat.id,
            'name': cat.name,
            'description': cat.description or '',
            'product_count': cat_prods.count(),
            'stock_units': cat_units,
            'total_value': round(cat_val, 2),
        })

    recent_bills = bills[:12]

    context = {
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'shop_phone': "+91 98765 43210",
        'shop_address': "Main Road, Near Old Bus Stand, Hardware Market",
        'categories': categories,
        'category_analytics': category_analytics,
        'products': products,
        'recent_bills': recent_bills,
        'expenses': expenses,
        'suppliers': suppliers,
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'total_balance': total_balance,
        'total_invoices': total_invoices,
        'total_products_count': total_products_count,
        'today_sales': daily_sales,
        'daily_sales': daily_sales,
        'daily_invoices_count': daily_invoices_count,
        'weekly_sales': weekly_sales,
        'weekly_invoices_count': weekly_invoices_count,
        'monthly_sales': monthly_sales,
        'monthly_invoices_count': monthly_invoices_count,
        'yearly_sales': yearly_sales,
        'yearly_invoices_count': yearly_invoices_count,
        'current_year': today.year,
        'current_month_name': today.strftime('%B'),
        'total_inventory_value': total_inventory_value,
        'total_stock_units': total_stock_units,
        'low_stock_products': low_stock_products,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'total_supplier_dues': total_supplier_dues,
        'cash_total': cash_total,
        'upi_total': upi_total,
        'card_total': card_total,
        'credit_total': credit_total,
        'net_banking_online_total': net_banking_online_total,
        'completed_paid_count': completed_paid_count,
        'high_80_count': high_80_count,
        'high_50_count': high_50_count,
        'down_50_count': down_50_count,
        'no_paid_count': no_paid_count,
        'expense_categories': Expense.EXPENSE_CATEGORIES,
        'expense_payment_modes': Expense.PAYMENT_MODES,
        'featured_offers': featured_offers,
        'featured_offers_count': featured_offers_count,
        'calendar_sales_json': calendar_sales_json,
    }
    return render(request, 'law/admindashboard.html', context)


@csrf_exempt
def add_category_api(request):
    """API to create a new category directly from the Admin Dashboard."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        description = (data.get('description') or '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Category name is required.'}, status=400)

        if Category.objects.filter(name__iexact=name).exists():
            return JsonResponse({
                'status': 'error',
                'is_duplicate': True,
                'message': f'This category "{name}" is already added! Duplicate category is not allowed.'
            }, status=400)

        cat = Category.objects.create(name=name, description=description)
        return JsonResponse({
            'status': 'success',
            'message': f'Category "{cat.name}" created successfully!',
            'category_id': cat.id,
            'name': cat.name
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def add_expense_api(request):
    """API to record a new business expense from the Admin Dashboard."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        title = (data.get('title') or '').strip()
        category = data.get('category', 'OTHER')
        amount = float(data.get('amount', 0) or 0)
        payment_mode = data.get('payment_mode', 'CASH')
        reference_no = (data.get('reference_no') or '').strip()
        notes = (data.get('notes') or '').strip()
        expense_date_str = data.get('expense_date')

        if not title:
            return JsonResponse({'status': 'error', 'message': 'Expense title is required.'}, status=400)
        if amount <= 0:
            return JsonResponse({'status': 'error', 'message': 'Amount must be greater than zero.'}, status=400)

        expense = Expense(
            title=title,
            category=category,
            amount=amount,
            payment_mode=payment_mode,
            reference_no=reference_no,
            notes=notes
        )
        if expense_date_str:
            expense.expense_date = expense_date_str

        expense.save()
        return JsonResponse({
            'status': 'success',
            'message': f'Expense "{expense.title}" of ₹{expense.amount} recorded successfully!',
            'expense_id': expense.id,
            'title': expense.title,
            'amount': float(expense.amount),
            'category': expense.get_category_display()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_expense_api(request, expense_id):
    """API to delete an expense record."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        expense = get_object_or_404(Expense, id=expense_id)
        title = expense.title
        expense.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Expense "{title}" deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def add_supplier_api(request):
    """API to add a new supplier/vendor from the Admin Dashboard."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        company_name = (data.get('company_name') or '').strip()
        phone = (data.get('phone') or '').strip()
        email = (data.get('email') or '').strip()
        address = (data.get('address') or '').strip()
        gstin = (data.get('gstin') or '').strip()
        supply_category = (data.get('supply_category') or 'Pipes & Fittings').strip()
        balance_due = float(data.get('balance_due', 0) or 0)
        notes = (data.get('notes') or '').strip()

        if not company_name or not name:
            return JsonResponse({'status': 'error', 'message': 'Company name and contact person are required.'}, status=400)

        supplier = Supplier.objects.create(
            name=name,
            company_name=company_name,
            phone=phone,
            email=email,
            address=address,
            gstin=gstin,
            supply_category=supply_category,
            balance_due=balance_due,
            notes=notes
        )
        return JsonResponse({
            'status': 'success',
            'message': f'Supplier "{supplier.company_name}" added successfully!',
            'supplier_id': supplier.id,
            'company_name': supplier.company_name
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_supplier_api(request, supplier_id):
    """API to delete a supplier record."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        supplier = get_object_or_404(Supplier, id=supplier_id)
        comp = supplier.company_name
        supplier.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Supplier "{comp}" deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def quick_stock_update_api(request, product_id):
    """API to quickly add stock to a product from low stock alerts or dashboard."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        prod = get_object_or_404(Product, id=product_id)
        add_quantity = int(data.get('add_quantity', 0))
        new_rate = data.get('rate')

        if add_quantity > 0:
            prod.quantity += add_quantity
        if new_rate is not None and float(new_rate) > 0:
            prod.rate = float(new_rate)

        prod.save()
        return JsonResponse({
            'status': 'success',
            'message': f'Stock updated for "{prod.name} ({prod.size})". New Stock: {prod.quantity} units!',
            'product_id': prod.id,
            'quantity': prod.quantity,
            'rate': float(prod.rate),
            'total': float(prod.total)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# =====================================================================
# AUTHENTICATION (LOGIN ONLY - NO SIGN UP)
# =====================================================================

@csrf_exempt
def api_login_view(request):
    """
    Login endpoint: Validates credentials (username & password only, NO sign up).
    On successful login, returns redirect_url to billing_pos (/pos/).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed.'}, status=405)
    try:
        data = json.loads(request.body)
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not username or not password:
            return JsonResponse({'status': 'error', 'message': 'Please enter both username and password.'}, status=400)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return JsonResponse({
                'status': 'success',
                'message': f'Welcome back, {user.username}! Login successful. Redirecting to POS Billing...',
                'redirect_url': '/pos/'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Sorry, you are not the shop owner!'
            }, status=401)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def login_view(request):
    """
    Standalone Login Page (NO sign up).
    Redirects directly to POS Billing upon successful login.
    """
    if request.user.is_authenticated:
        return redirect('billing_pos')

    error_message = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect('billing_pos')
        else:
            error_message = 'Sorry, you are not the shop owner!'

    return render(request, 'law/login.html', {
        'shop_name': "ZAM ZAM HARDWARE",
        'shop_owner': "Lawrence C",
        'error': error_message,
        'error_message': error_message
    })


def logout_view(request):
    """
    Logs out the current session and redirects to homepage.
    """
    auth_logout(request)
    return redirect('index')


# =====================================================================
# BACKEND ADMIN APIS FOR HOMEPAGE FEATURED OFFER PRODUCTS (4 CARDS)
# =====================================================================

@csrf_exempt
def add_featured_offer_api(request):
    """
    API for Admin to create a new Featured Offer Product on the homepage.
    Only admin can add these details to the backend.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        category_name = (data.get('category_name') or 'Valves & Fittings').strip()
        size = (data.get('size') or 'Standard').strip()
        image_url = (data.get('image_url') or '').strip()
        original_price = float(data.get('original_price', 0) or 0)
        discount_price = float(data.get('discount_price', 0) or 0)
        offer_date = (data.get('offer_date') or '30 Nov 2026').strip()
        description = (data.get('description') or '').strip()
        button_text = (data.get('button_text') or '🛒 Add to Bill / Enquire').strip()
        button_link = (data.get('button_link') or '/pos/').strip()
        order = int(data.get('order', 1) or 1)

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Product offer name is required.'}, status=400)

        # Check for duplicate offer card
        if FeaturedOfferProduct.objects.filter(name__iexact=name, size__iexact=size).exists():
            return JsonResponse({
                'status': 'error',
                'is_duplicate': True,
                'message': f'This featured offer "{name} ({size})" is already added! Duplicate offer cards are not allowed.'
            }, status=400)

        offer = FeaturedOfferProduct.objects.create(
            name=name,
            category_name=category_name,
            size=size,
            image_url=image_url or "https://images.unsplash.com/photo-1585704032915-c3400ca199e7?auto=format&fit=crop&w=600&q=80",
            original_price=original_price,
            discount_price=discount_price,
            offer_date=offer_date,
            description=description,
            button_text=button_text,
            button_link=button_link,
            order=order,
            is_active=True
        )
        return JsonResponse({
            'status': 'success',
            'message': f'Featured Offer Product "{offer.name}" added successfully by Admin!',
            'offer_id': offer.id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_featured_offer_api(request, offer_id):
    """
    API for Admin to delete a Featured Offer Product from the homepage.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST allowed'}, status=405)
    try:
        offer = get_object_or_404(FeaturedOfferProduct, id=offer_id)
        name = offer.name
        offer.delete()
        return JsonResponse({
            'status': 'success',
            'message': f'Featured Offer Product "{name}" deleted successfully!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



