import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plumbing.settings')
django.setup()

from django.contrib.auth.models import User
from law.models import Category, Product

# Create superuser for Jebin
if not User.objects.filter(username='jebin').exists():
    User.objects.create_superuser('jebin', 'jebin@example.com', 'jebin123')
    print("Superuser created -> Username: jebin | Password: jebin123")
else:
    print("Superuser 'jebin' already exists")

data = [
    {
        'category': 'PVC Pipes & Fittings',
        'desc': 'Rigid polyvinyl chloride pipes, elbows, tees and sockets for cold water plumbing',
        'products': [
            {'name': 'PVC Pipe (4m length)', 'size': '1/2 inch', 'rate': 120.00, 'qty': 50},
            {'name': 'PVC Pipe (4m length)', 'size': '3/4 inch', 'rate': 165.00, 'qty': 45},
            {'name': 'PVC Pipe (4m length)', 'size': '1 inch', 'rate': 230.00, 'qty': 30},
            {'name': 'PVC Elbow 90 Degree', 'size': '1/2 inch', 'rate': 18.00, 'qty': 150},
            {'name': 'PVC Elbow 90 Degree', 'size': '3/4 inch', 'rate': 26.00, 'qty': 120},
            {'name': 'PVC Equal Tee', 'size': '3/4 inch', 'rate': 32.00, 'qty': 100},
            {'name': 'PVC Reducer Bush', 'size': '1 to 3/4 inch', 'rate': 22.00, 'qty': 80},
        ]
    },
    {
        'category': 'CPVC Pipes & Fittings',
        'desc': 'Chlorinated PVC pipes and brass insert fittings for hot and cold water',
        'products': [
            {'name': 'CPVC Pipe SDR 11 (3m)', 'size': '3/4 inch', 'rate': 210.00, 'qty': 40},
            {'name': 'CPVC Brass FTA', 'size': '1/2 inch', 'rate': 85.00, 'qty': 60},
            {'name': 'CPVC Brass MTA', 'size': '3/4 inch', 'rate': 95.00, 'qty': 55},
            {'name': 'CPVC Concealed Valve', 'size': '3/4 inch', 'rate': 390.00, 'qty': 18},
        ]
    },
    {
        'category': 'Brass Valves & Fittings',
        'desc': 'Heavy-duty brass ball valves, check valves and gate valves',
        'products': [
            {'name': 'Brass Full Flow Ball Valve', 'size': '1/2 inch', 'rate': 220.00, 'qty': 35},
            {'name': 'Brass Full Flow Ball Valve', 'size': '3/4 inch', 'rate': 310.00, 'qty': 25},
            {'name': 'Heavy Brass Gate Valve', 'size': '1 inch', 'rate': 450.00, 'qty': 15},
            {'name': 'Brass Non-Return Check Valve', 'size': '1 inch', 'rate': 380.00, 'qty': 20},
        ]
    },
    {
        'category': 'Taps, Faucets & Showers',
        'desc': 'Bib cocks, pillar cocks, angle valves and overhead showers',
        'products': [
            {'name': 'Bib Cock Tap Long Body', 'size': '1/2 inch', 'rate': 340.00, 'qty': 30},
            {'name': 'Chrome Angle Stop Cock', 'size': '1/2 inch', 'rate': 280.00, 'qty': 40},
            {'name': 'Pillar Cock for Wash Basin', 'size': '1/2 inch', 'rate': 490.00, 'qty': 20},
            {'name': 'Rain Overhead Shower Head', 'size': '6 inch x 6 inch', 'rate': 620.00, 'qty': 12},
        ]
    },
    {
        'category': 'Sealants, Adhesives & Tapes',
        'desc': 'Teflon tapes, PVC solvent cements, silicone sealants and thread glues',
        'products': [
            {'name': 'PTFE Teflon Thread Seal Tape', 'size': '12mm x 10m', 'rate': 25.00, 'qty': 200},
            {'name': 'PVC Solvent Cement Tin', 'size': '100 ml', 'rate': 65.00, 'qty': 50},
            {'name': 'CPVC High Strength Solvent', 'size': '118 ml', 'rate': 110.00, 'qty': 35},
            {'name': 'Clear Silicone Sealant Tube', 'size': '280 ml', 'rate': 185.00, 'qty': 25},
        ]
    },
    {
        'category': 'Sanitary & Drainage',
        'desc': 'Flexible waste pipes, floor drains, traps and connection hoses',
        'products': [
            {'name': 'Flexible Sink Waste Pipe', 'size': '1.25 inch', 'rate': 75.00, 'qty': 45},
            {'name': 'Stainless Steel Floor Drain Jali', 'size': '5 inch round', 'rate': 140.00, 'qty': 60},
            {'name': 'SS Braided Connection Hose Pipe', 'size': '18 inch', 'rate': 130.00, 'qty': 50},
        ]
    },
    {
        'category': 'Plumbing Tools & Hardware',
        'desc': 'Pipe wrenches, thread sealers, cutters and hardware accessories',
        'products': [
            {'name': 'Heavy Duty Pipe Wrench', 'size': '12 inch', 'rate': 380.00, 'qty': 8},
            {'name': 'Heavy Duty Pipe Wrench', 'size': '14 inch', 'rate': 490.00, 'qty': 6},
            {'name': 'PVC Pipe Scissor Cutter', 'size': 'Up to 42mm', 'rate': 260.00, 'qty': 15},
            {'name': 'SS Pipe Clamps Pack (10 pcs)', 'size': '3/4 inch', 'rate': 120.00, 'qty': 40},
        ]
    }
]

for item in data:
    cat, _ = Category.objects.get_or_create(
        name=item['category'],
        defaults={'description': item['desc']}
    )
    for p in item['products']:
        Product.objects.get_or_create(
            category=cat,
            name=p['name'],
            size=p['size'],
            defaults={'rate': p['rate'], 'quantity': p['qty']}
        )

print(f"Seed successfully finished! Categories: {Category.objects.count()} | Products: {Product.objects.count()}")
