from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from inventory.models import Product, Warehouse, Stock
from inventory.services import register_movement

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
