from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import Category, Customer, PaymentMethod, Product, Purchase, Sale, Stock, StockMovement, Supplier, UserProfile, Warehouse
from .permissions import role_required
from .reports import build_sales_summary, products_csv
from .importers import import_products_csv
from .services import cancel_sale, create_purchase, create_sale, customer_balance, record_customer_payment, record_supplier_payment, register_movement, return_sale, supplier_balance, transfer_stock

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
@role_required('admin', 'manager')
def product_create(request):
    if request.method == 'POST':
        category, _ = Category.objects.get_or_create(name=request.POST.get('category', 'General').strip() or 'General')
        Product.objects.create(sku=request.POST['sku'].strip(), name=request.POST['name'].strip(), category=category, unit_label=request.POST.get('unit_label', 'unidad'), cost=request.POST.get('cost') or 0, sale_price=request.POST.get('sale_price') or 0, min_stock=request.POST.get('min_stock') or 0, cost_method=request.POST.get('cost_method', 'weighted_average'))
        messages.success(request, 'Producto creado correctamente.')
        return redirect('products')
    return render(request, 'inventory/product_form.html')

@login_required
@role_required('admin', 'manager', 'warehouse')
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
@role_required('admin', 'manager', 'seller')
def sale_create(request):
    products = Product.objects.filter(active=True).order_by('name')
    warehouses = Warehouse.objects.filter(active=True).order_by('name')
    customers = Customer.objects.order_by('name')
    payment_methods = PaymentMethod.objects.filter(active=True)
    if request.method == 'POST':
        try:
            product_ids = request.POST.getlist('product')
            quantities = request.POST.getlist('quantity')
            comments = request.POST.getlist('comment')
            lines = [(get_object_or_404(Product, pk=product_id), quantity, comments[index] if index < len(comments) else '') for index, (product_id, quantity) in enumerate(zip(product_ids, quantities))]
            if not lines:
                raise ValueError('Agregá al menos un producto a la venta.')
            warehouse = get_object_or_404(Warehouse, pk=request.POST['warehouse'])
            payment_method = PaymentMethod.objects.filter(pk=request.POST.get('payment_method'), active=True).first() if request.POST.get('payment_method') else None
            sale = create_sale(warehouse=warehouse, customer=Customer.objects.filter(pk=request.POST.get('customer')).first() if request.POST.get('customer') else None, payment_method=payment_method, user=request.user, lines=lines, consume_recipe=request.POST.get('consume_recipe') == 'on', notes=request.POST.get('notes', ''))
            messages.success(request, f'Venta #{sale.pk} registrada. Total: $ {sale.total:.2f}')
            return redirect('sale_receipt', sale_id=sale.pk)
        except (ValueError, KeyError) as error:
            messages.error(request, str(error))
    return render(request, 'inventory/sale_form.html', {'products': products, 'warehouses': warehouses, 'customers': customers, 'payment_methods': payment_methods})

@login_required
def sale_receipt(request, sale_id):
    sale = get_object_or_404(Sale.objects.select_related('warehouse', 'customer').prefetch_related('items__product'), pk=sale_id)
    return render(request, 'inventory/sale_receipt.html', {'sale': sale})

@login_required
def sale_list(request):
    sales = Sale.objects.select_related('warehouse', 'customer').prefetch_related('items')[:50]
    return render(request, 'inventory/sales.html', {'sales': sales})

@login_required
@role_required('admin', 'manager')
def sale_cancel(request, sale_id):
    if request.method == 'POST':
        try:
            cancel_sale(sale=get_object_or_404(Sale, pk=sale_id))
            messages.success(request, 'Venta anulada y stock reintegrado.')
        except ValueError as error:
            messages.error(request, str(error))
    return redirect('sale_receipt', sale_id=sale_id)

@login_required
@role_required('admin', 'manager')
def sale_return(request, sale_id):
    if request.method == 'POST':
        try:
            return_sale(sale=get_object_or_404(Sale, pk=sale_id), reason=request.POST.get('reason', '').strip())
            messages.success(request, 'Devolución registrada y stock reintegrado.')
        except ValueError as error:
            messages.error(request, str(error))
    return redirect('sale_receipt', sale_id=sale_id)

@login_required
@role_required('admin', 'manager')
def purchase_create(request):
    products = Product.objects.filter(active=True).order_by('name')
    warehouses = Warehouse.objects.filter(active=True).order_by('name')
    suppliers = Supplier.objects.order_by('name')
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, pk=request.POST['product'])
            warehouse = get_object_or_404(Warehouse, pk=request.POST['warehouse'])
            supplier = Supplier.objects.filter(pk=request.POST.get('supplier')).first() if request.POST.get('supplier') else None
            purchase = create_purchase(supplier=supplier, warehouse=warehouse, user=request.user, lines=[(product, request.POST['quantity'], request.POST['unit_cost'])], notes=request.POST.get('notes', ''))
            messages.success(request, f'Compra #{purchase.pk} registrada. Stock actualizado.')
            return redirect('dashboard')
        except (ValueError, KeyError) as error:
            messages.error(request, str(error))
    return render(request, 'inventory/purchase_form.html', {'products': products, 'warehouses': warehouses, 'suppliers': suppliers})

@login_required
@role_required('admin', 'manager', 'warehouse')
def transfer_create(request):
    products = Product.objects.filter(active=True).order_by('name')
    warehouses = Warehouse.objects.filter(active=True).order_by('name')
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, pk=request.POST['product'])
            source = get_object_or_404(Warehouse, pk=request.POST['source'])
            target = get_object_or_404(Warehouse, pk=request.POST['target'])
            if source == target:
                raise ValueError('El depósito de origen y destino deben ser diferentes.')
            transfer_stock(product=product, source=source, target=target, quantity=request.POST['quantity'], user=request.user, notes=request.POST.get('notes', ''))
            messages.success(request, 'Transferencia registrada correctamente.')
            return redirect('dashboard')
        except (ValueError, KeyError) as error:
            messages.error(request, str(error))
    return render(request, 'inventory/transfer_form.html', {'products': products, 'warehouses': warehouses})

@login_required
def set_language(request):
    language = request.POST.get('language', 'es')
    if language not in {'es', 'en'}:
        language = 'es'
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    profile.language = language
    profile.save(update_fields=['language'])
    request.session['django_language'] = language
    return redirect(request.POST.get('next') or request.META.get('HTTP_REFERER') or 'dashboard')

@login_required
def reports(request):
    start = request.GET.get('start') or None
    end = request.GET.get('end') or None
    end_exclusive = datetime.strptime(end, '%Y-%m-%d') + timedelta(days=1) if end else None
    return render(request, 'inventory/reports.html', {'summary': build_sales_summary(start=start, end=end_exclusive), 'start': start or '', 'end': end or ''})

@login_required
def products_export_csv(request):
    response = HttpResponse(products_csv(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="stockpilot-productos.csv"'
    return response

@login_required
@role_required('admin', 'manager')
def products_import(request):
    result = None
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            content = request.FILES['file'].read().decode('utf-8-sig')
            result = import_products_csv(content)
            if result['errors']:
                messages.warning(request, f"Importación finalizada con {len(result['errors'])} error(es).")
            else:
                messages.success(request, f"Importación completada: {result['created']} creados, {result['updated']} actualizados.")
        except UnicodeDecodeError:
            result = {'errors': ['El archivo debe estar guardado como CSV UTF-8.']}
            messages.error(request, result['errors'][0])
    return render(request, 'inventory/products_import.html', {'result': result})

@login_required
def current_accounts(request):
    customers = [(customer, customer_balance(customer)) for customer in Customer.objects.order_by('name')]
    suppliers = [(supplier, supplier_balance(supplier)) for supplier in Supplier.objects.order_by('name')]
    return render(request, 'inventory/current_accounts.html', {'customers': customers, 'suppliers': suppliers})

@login_required
@role_required('admin', 'manager')
def account_payment(request):
    if request.method == 'POST':
        amount = request.POST.get('amount', '0')
        note = request.POST.get('note', '')
        if request.POST.get('customer'):
            record_customer_payment(customer=get_object_or_404(Customer, pk=request.POST['customer']), amount=amount, note=note)
        elif request.POST.get('supplier'):
            record_supplier_payment(supplier=get_object_or_404(Supplier, pk=request.POST['supplier']), amount=amount, note=note)
        messages.success(request, 'Pago registrado en la cuenta corriente.')
    return redirect('current_accounts')
