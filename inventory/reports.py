import csv
from decimal import Decimal
from io import StringIO
from django.utils import timezone
from .models import Product, Sale, Stock

def build_sales_summary(*, start=None, end=None):
    sales = Sale.objects.filter(status='paid').prefetch_related('items__product')
    if start:
        sales = sales.filter(created_at__gte=start)
    if end:
        sales = sales.filter(created_at__lt=end)
    revenue = Decimal('0')
    cost = Decimal('0')
    count = 0
    for sale in sales:
        count += 1
        for item in sale.items.all():
            revenue += item.subtotal
            cost += item.quantity * item.product.cost
    return {'sales_count': count, 'revenue': revenue, 'cost': cost, 'gross_profit': revenue - cost}

def products_csv():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['SKU', 'Producto', 'Categoría', 'Costo', 'Precio venta', 'Margen %', 'Stock total'])
    products = Product.objects.filter(active=True).select_related('category').prefetch_related('stocks')
    for product in products:
        stock = sum((item.quantity for item in product.stocks.all()), Decimal('0'))
        writer.writerow([product.sku, product.name, product.category.name if product.category else 'General', product.cost, product.sale_price, product.margin, stock])
    return output.getvalue()
