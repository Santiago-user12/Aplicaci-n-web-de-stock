from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.core import mail
from inventory.models import Product, Warehouse, Stock, Recipe, RecipeItem, Sale, Supplier, UserProfile, PaymentMethod, Customer, CustomerAccountEntry, SupplierAccountEntry
from inventory.services import register_movement, create_sale, create_purchase, transfer_stock, cancel_sale, return_sale, record_customer_charge, record_customer_payment, record_supplier_invoice, record_supplier_payment, reconcile_customer_entry, reconcile_supplier_entry
from inventory.reports import build_sales_summary
from io import BytesIO
from openpyxl import Workbook
from inventory.importers import import_products_csv, import_products_xlsx

@pytest.mark.django_db
def test_purchase_updates_stock_and_weighted_cost():
    product = Product.objects.create(sku='CAF-1', name='Café', cost=Decimal('10'), cost_method='weighted_average')
    warehouse = Warehouse.objects.create(name='Central', code='CENTRAL')
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=10, unit_cost=20)
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=10, unit_cost=30)
    stock = Stock.objects.get(product=product, warehouse=warehouse)
    product.refresh_from_db()
    assert stock.quantity == Decimal('20.000')
    assert product.cost == Decimal('25')

@pytest.mark.django_db
def test_sale_cannot_exceed_available_stock():
    product = Product.objects.create(sku='PAN-1', name='Pan')
    warehouse = Warehouse.objects.create(name='Local', code='LOCAL')
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=2, unit_cost=5)
    with pytest.raises(ValueError, match='Stock insuficiente'):
        register_movement(product=product, warehouse=warehouse, movement_type='sale', quantity=3)

@pytest.mark.django_db
def test_sale_consumes_recipe_ingredients_and_returns_total():
    dish = Product.objects.create(sku='PIZ-1', name='Pizza', sale_price=Decimal('1200'))
    flour = Product.objects.create(sku='HAR-1', name='Harina', cost=Decimal('100'))
    cheese = Product.objects.create(sku='QUE-1', name='Queso', cost=Decimal('500'))
    warehouse = Warehouse.objects.create(name='Cocina', code='COCINA')
    register_movement(product=flour, warehouse=warehouse, movement_type='purchase', quantity=10, unit_cost=100)
    register_movement(product=cheese, warehouse=warehouse, movement_type='purchase', quantity=10, unit_cost=500)
    register_movement(product=dish, warehouse=warehouse, movement_type='purchase', quantity=3, unit_cost=600)
    recipe = Recipe.objects.create(product=dish, yield_quantity=1)
    RecipeItem.objects.create(recipe=recipe, ingredient=flour, quantity=2)
    RecipeItem.objects.create(recipe=recipe, ingredient=cheese, quantity=1)
    sale = create_sale(warehouse=warehouse, lines=[(dish, 1)], consume_recipe=True)
    assert sale.total == Decimal('1200')
    assert Stock.objects.get(product=flour, warehouse=warehouse).quantity == Decimal('8.000')
    assert Stock.objects.get(product=cheese, warehouse=warehouse).quantity == Decimal('9.000')
    assert Stock.objects.get(product=dish, warehouse=warehouse).quantity == Decimal('2.000')

@pytest.mark.django_db
def test_sale_accepts_multiple_lines():
    first = Product.objects.create(sku='A-1', name='Producto A', sale_price=Decimal('10'))
    second = Product.objects.create(sku='B-1', name='Producto B', sale_price=Decimal('25'))
    warehouse = Warehouse.objects.create(name='Local', code='MULTI')
    register_movement(product=first, warehouse=warehouse, movement_type='purchase', quantity=5, unit_cost=4)
    register_movement(product=second, warehouse=warehouse, movement_type='purchase', quantity=5, unit_cost=12)
    sale = create_sale(warehouse=warehouse, lines=[(first, 2), (second, 1)])
    assert sale.items.count() == 2
    assert sale.total == Decimal('45')

@pytest.mark.django_db
def test_purchase_from_supplier_updates_stock_and_cost():
    product = Product.objects.create(sku='ACE-1', name='Aceite', cost=Decimal('10'))
    supplier = Supplier.objects.create(name='Proveedor Central')
    warehouse = Warehouse.objects.create(name='Depósito', code='DEP')
    purchase = create_purchase(supplier=supplier, warehouse=warehouse, lines=[(product, 12, 18)])
    product.refresh_from_db()
    assert purchase.total == Decimal('216')
    assert Stock.objects.get(product=product, warehouse=warehouse).quantity == Decimal('12.000')
    assert product.cost == Decimal('18')

@pytest.mark.django_db
def test_transfer_moves_stock_between_warehouses():
    product = Product.objects.create(sku='TR-1', name='Producto transferible', cost=Decimal('20'))
    source = Warehouse.objects.create(name='Central', code='SRC')
    target = Warehouse.objects.create(name='Sucursal', code='DST')
    register_movement(product=product, warehouse=source, movement_type='purchase', quantity=10, unit_cost=20)
    transfer_stock(product=product, source=source, target=target, quantity=4)
    assert Stock.objects.get(product=product, warehouse=source).quantity == Decimal('6.000')
    assert Stock.objects.get(product=product, warehouse=target).quantity == Decimal('4.000')

@pytest.mark.django_db
def test_user_can_change_personal_language():
    user = get_user_model().objects.create_user(username='cliente', password='secret')
    profile = UserProfile.objects.create(user=user)
    client = Client()
    client.force_login(user)
    response = client.post('/idioma/', {'language': 'en'}, follow=True)
    profile.refresh_from_db()
    assert response.status_code == 200
    assert profile.language == 'en'
    assert client.session['django_language'] == 'en'
    assert response.headers['Content-Language'] == 'en'

@pytest.mark.django_db
def test_public_mode_allows_purchase_and_sale_without_login():
    client = Client()
    assert client.get('/compras/nueva/').status_code == 200
    assert client.get('/ventas/nueva/').status_code == 200

@pytest.mark.django_db
def test_public_mode_allows_dashboard_without_login():
    client = Client()
    assert client.get('/').status_code == 200
    assert client.get('/movimientos/nuevo/').status_code == 200

@pytest.mark.django_db
def test_public_mode_does_not_require_login():
    client = Client()
    assert client.get('/login/').status_code == 404
    assert client.get('/cuenta/olvide-contrasena/').status_code == 404

@pytest.mark.django_db
def test_sale_stores_payment_method_and_line_comments():
    product = Product.objects.create(sku='PAY-1', name='Producto pago', sale_price=Decimal('100'))
    warehouse = Warehouse.objects.create(name='Caja', code='PAY')
    payment = PaymentMethod.objects.create(name='Transferencia bancaria')
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=3, unit_cost=40)
    sale = create_sale(warehouse=warehouse, lines=[(product, 2, 'Sin envoltorio')], payment_method=payment)
    sale.refresh_from_db()
    assert sale.payment_method == payment
    assert sale.items.get().comment == 'Sin envoltorio'
    assert sale.total == Decimal('200')

@pytest.mark.django_db
def test_cancel_sale_restores_stock_and_blocks_second_cancellation():
    product = Product.objects.create(sku='DEV-1', name='Producto devuelto', sale_price=Decimal('50'))
    warehouse = Warehouse.objects.create(name='Local', code='DEV')
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=5, unit_cost=20)
    sale = create_sale(warehouse=warehouse, lines=[(product, 2)])
    cancel_sale(sale=sale)
    assert Stock.objects.get(product=product, warehouse=warehouse).quantity == Decimal('5.000')
    sale.refresh_from_db()
    assert sale.status == 'cancelled'
    with pytest.raises(ValueError, match='ya fue anulada'):
        cancel_sale(sale=sale)

@pytest.mark.django_db
def test_return_sale_restores_stock_and_marks_cancelled():
    product = Product.objects.create(sku='DEV-2', name='Producto para devolución', sale_price=Decimal('80'))
    warehouse = Warehouse.objects.create(name='Local', code='DEV2')
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=4, unit_cost=30)
    sale = create_sale(warehouse=warehouse, lines=[(product, 1)])
    return_sale(sale=sale, reason='Cliente cambió de opinión')
    sale.refresh_from_db()
    assert sale.status == 'cancelled'
    assert 'Cliente cambió de opinión' in sale.notes
    assert Stock.objects.get(product=product, warehouse=warehouse).quantity == Decimal('4.000')

@pytest.mark.django_db
def test_sales_summary_reports_revenue_cost_and_profit():
    product = Product.objects.create(sku='REP-1', name='Reportable', cost=Decimal('30'), sale_price=Decimal('80'))
    warehouse = Warehouse.objects.create(name='Reportes', code='REP')
    register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=4, unit_cost=30)
    create_sale(warehouse=warehouse, lines=[(product, 2)])
    summary = build_sales_summary()
    assert summary['sales_count'] == 1
    assert summary['revenue'] == Decimal('160')
    assert summary['cost'] == Decimal('60')
    assert summary['gross_profit'] == Decimal('100')

@pytest.mark.django_db
def test_import_products_csv_creates_products_and_stock():
    warehouse = Warehouse.objects.create(name='Importación', code='IMP')
    csv_text = 'SKU,Producto,Categoría,Costo,Precio venta,Stock,Depósito\nCSV-1,Producto importado,Almacén,12.50,25,7,IMP\n'
    result = import_products_csv(csv_text)
    product = Product.objects.get(sku='CSV-1')
    assert result == {'created': 1, 'updated': 0, 'stock_rows': 1, 'errors': []}
    assert product.name == 'Producto importado'
    assert Stock.objects.get(product=product, warehouse=warehouse).quantity == Decimal('7.000')

@pytest.mark.django_db
def test_import_products_xlsx_uses_same_catalog_contract():
    warehouse = Warehouse.objects.create(name='Excel', code='XLSX')
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['SKU', 'Producto', 'Categoría', 'Costo', 'Precio venta', 'Stock', 'Depósito'])
    sheet.append(['XLSX-1', 'Producto Excel', 'Oficina', 10, 20, 4, 'XLSX'])
    file_data = BytesIO()
    workbook.save(file_data)
    result = import_products_xlsx(file_data.getvalue())
    assert result['created'] == 1
    assert Product.objects.get(sku='XLSX-1').name == 'Producto Excel'
    assert Stock.objects.get(product__sku='XLSX-1', warehouse=warehouse).quantity == Decimal('4.000')

@pytest.mark.django_db
def test_customer_and_supplier_current_accounts_track_balances():
    customer = Customer.objects.create(name='Cliente cuenta corriente')
    supplier = Supplier.objects.create(name='Proveedor cuenta corriente')
    record_customer_charge(customer=customer, amount=Decimal('1000'), note='Venta fiada')
    record_customer_payment(customer=customer, amount=Decimal('350'), note='Pago parcial')
    record_supplier_invoice(supplier=supplier, amount=Decimal('800'), note='Compra a crédito')
    record_supplier_payment(supplier=supplier, amount=Decimal('300'), note='Pago al proveedor')
    from inventory.services import customer_balance, supplier_balance
    assert customer_balance(customer) == Decimal('650')
    assert supplier_balance(supplier) == Decimal('500')

@pytest.mark.django_db
def test_account_entries_can_be_reconciled_with_external_reference():
    customer = Customer.objects.create(name='Conciliable')
    supplier = Supplier.objects.create(name='Proveedor conciliable')
    customer_entry = record_customer_payment(customer=customer, amount=Decimal('100'))
    supplier_entry = record_supplier_payment(supplier=supplier, amount=Decimal('200'))
    reconcile_customer_entry(entry=customer_entry, reference='BANCO-001')
    reconcile_supplier_entry(entry=supplier_entry, reference='BANCO-002')
    customer_entry.refresh_from_db(); supplier_entry.refresh_from_db()
    assert customer_entry.reconciled is True
    assert customer_entry.reference == 'BANCO-001'
    assert supplier_entry.reconciled is True
    assert supplier_entry.reference == 'BANCO-002'

