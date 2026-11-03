from decimal import Decimal
from django.db import transaction
from .models import Stock, StockMovement

INBOUND = {'purchase', 'adjustment_in', 'production'}

@transaction.atomic
def register_movement(*, product, warehouse, movement_type, quantity, unit_cost=Decimal('0'), user=None, reference='', notes=''):
    quantity = Decimal(str(quantity))
    stock, _ = Stock.objects.select_for_update().get_or_create(product=product, warehouse=warehouse)
    if movement_type in INBOUND:
        stock.quantity += quantity
        if unit_cost > 0:
            if stock.quantity > quantity and product.cost_method == 'weighted_average':
                previous = stock.quantity - quantity
                product.cost = ((product.cost * previous) + (unit_cost * quantity)) / stock.quantity
            else:
                product.cost = unit_cost
            product.save(update_fields=['cost'])
    else:
        if stock.available < quantity:
            raise ValueError(f'Stock insuficiente: disponible {stock.available}')
        stock.quantity -= quantity
    stock.save(update_fields=['quantity'])
    return StockMovement.objects.create(product=product, warehouse=warehouse, movement_type=movement_type, quantity=quantity, unit_cost=unit_cost, created_by=user, reference=reference, notes=notes)

def recipe_cost(recipe):
    return sum((item.cost for item in recipe.items.select_related('ingredient')), Decimal('0')) / (recipe.yield_quantity or Decimal('1'))
