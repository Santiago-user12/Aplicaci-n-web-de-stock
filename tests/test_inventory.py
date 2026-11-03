from decimal import Decimal
import pytest
from inventory.models import Product, Warehouse, Stock, Recipe, RecipeItem, Sale, Supplier, Purchase
from inventory.services import register_movement, create_sale, create_purchase, transfer_stock

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

