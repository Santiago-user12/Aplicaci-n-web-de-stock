from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.shortcuts import get_object_or_404, redirect, render
from .models import Category, Customer, Product, Sale, Stock, StockMovement, Warehouse
from .services import create_sale, register_movement

@login_required
def dashboard(request):
    products = Product.objects.filter(active=True).select_related('category')
    stock_total = Stock.objects.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    low_stock = Stock.objects.filter(quantity__lte=F('product__min_stock')).select_related('product', 'warehouse')
    inventory_value = sum((s.quantity * s.product.cost for s in Stock.objects.select_related('product')), Decimal('0'))
    context = {'products_count': products.count(), 'stock_total': stock_total, 'low_stock': low_stock[:8], 'inventory_value': inventory_value, 'recent_movements': StockMovement.objects.select_related('product', 'warehouse')[:8]}
    return render(request, 'inventory/dashboard.html', context)

@login_required
def product_list(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(active=True).select_related('category')
    if query:
        products = products.filter(name__icontains=query) | products.filter(sku__icontains=query)
    return render(request, 'inventory/products.html', {'products': products, 'query': query})

@login_required
def product_create(request):
    if request.method == 'POST':
        category, _ = Category.objects.get_or_create(name=request.POST.get('category', 'General').strip() or 'General')
        Product.objects.create(sku=request.POST['sku'].strip(), name=request.POST['name'].strip(), category=category, unit_label=request.POST.get('unit_label', 'unidad'), cost=request.POST.get('cost') or 0, sale_price=request.POST.get('sale_price') or 0, min_stock=request.POST.get('min_stock') or 0, cost_method=request.POST.get('cost_method', 'weighted_average'))
        messages.success(request, 'Producto creado correctamente.')
        return redirect('products')
    return render(request, 'inventory/product_form.html')

@login_required
def movement_create(request):
    products = Product.objects.filter(active=True).order_by('name')
    warehouses = Warehouse.objects.filter(active=True).order_by('name')
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, pk=request.POST['product'])
            warehouse = get_object_or_404(Warehouse, pk=request.POST['warehouse'])
            register_movement(product=product, warehouse=warehouse, movement_type=request.POST['movement_type'], quantity=request.POST['quantity'], unit_cost=Decimal(request.POST.get('unit_cost') or '0'), user=request.user, notes=request.POST.get('notes', ''))
            messages.success(request, 'Movimiento registrado y stock actualizado.')
            return redirect('dashboard')
        except (ValueError, KeyError) as error:
            messages.error(request, str(error))
    return render(request, 'inventory/movement_form.html', {'products': products, 'warehouses': warehouses, 'movement_types': StockMovement.TYPES})

@login_required
def sale_create(request):
    products = Product.objects.filter(active=True).order_by('name')
    warehouses = Warehouse.objects.filter(active=True).order_by('name')
    customers = Customer.objects.order_by('name')
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, pk=request.POST['product'])
            warehouse = get_object_or_404(Warehouse, pk=request.POST['warehouse'])
            sale = create_sale(warehouse=warehouse, customer=Customer.objects.filter(pk=request.POST.get('customer')).first() if request.POST.get('customer') else None, user=request.user, lines=[(product, request.POST['quantity'])], consume_recipe=request.POST.get('consume_recipe') == 'on', notes=request.POST.get('notes', ''))
            messages.success(request, f'Venta #{sale.pk} registrada. Total: $ {sale.total:.2f}')
            return redirect('sale_receipt', sale_id=sale.pk)
        except (ValueError, KeyError) as error:
            messages.error(request, str(error))
    return render(request, 'inventory/sale_form.html', {'products': products, 'warehouses': warehouses, 'customers': customers})

@login_required
def sale_receipt(request, sale_id):
    sale = get_object_or_404(Sale.objects.select_related('warehouse', 'customer').prefetch_related('items__product'), pk=sale_id)
    return render(request, 'inventory/sale_receipt.html', {'sale': sale})
