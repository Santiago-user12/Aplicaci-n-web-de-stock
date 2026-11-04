from decimal import Decimal
from django.db import transaction
from .models import Purchase, PurchaseItem, Sale, SaleItem, Stock, StockMovement

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

@transaction.atomic
def create_sale(*, warehouse, lines, customer=None, user=None, consume_recipe=False, notes=''):
    """Create a sale and discount finished goods; optionally discount recipe ingredients."""
    sale = Sale.objects.create(warehouse=warehouse, customer=customer, created_by=user, notes=notes)
    for product, quantity in lines:
        quantity = Decimal(str(quantity))
        register_movement(product=product, warehouse=warehouse, movement_type='sale', quantity=quantity, unit_cost=product.cost, user=user, reference=f'SALE-{sale.pk}')
        SaleItem.objects.create(sale=sale, product=product, quantity=quantity, unit_price=product.sale_price)
        if consume_recipe and hasattr(product, 'recipe'):
            recipe = product.recipe
            multiplier = quantity / (recipe.yield_quantity or Decimal('1'))
            for item in recipe.items.select_related('ingredient'):
                ingredient_quantity = item.quantity * multiplier
                register_movement(product=item.ingredient, warehouse=warehouse, movement_type='sale', quantity=ingredient_quantity, unit_cost=item.ingredient.cost, user=user, reference=f'SALE-{sale.pk}', notes=f'Ingrediente de {product.name}')
    return sale

def recipe_cost(recipe):
    return sum((item.cost for item in recipe.items.select_related('ingredient')), Decimal('0')) / (recipe.yield_quantity or Decimal('1'))

@transaction.atomic
def create_purchase(*, supplier, warehouse, lines, user=None, notes=''):
    purchase = Purchase.objects.create(supplier=supplier, warehouse=warehouse, created_by=user, notes=notes)
    for product, quantity, unit_cost in lines:
        quantity, unit_cost = Decimal(str(quantity)), Decimal(str(unit_cost))
        register_movement(product=product, warehouse=warehouse, movement_type='purchase', quantity=quantity, unit_cost=unit_cost, user=user, reference=f'PURCHASE-{purchase.pk}')
        PurchaseItem.objects.create(purchase=purchase, product=product, quantity=quantity, unit_cost=unit_cost)
    return purchase

@transaction.atomic
def transfer_stock(*, product, source, target, quantity, user=None, notes=''):
    quantity = Decimal(str(quantity))
    reference = f'TRANSFER-{product.sku}-{source.code}-{target.code}'
    register_movement(product=product, warehouse=source, movement_type='transfer', quantity=quantity, unit_cost=product.cost, user=user, reference=reference, notes=notes)
    register_movement(product=product, warehouse=target, movement_type='adjustment_in', quantity=quantity, unit_cost=product.cost, user=user, reference=reference, notes=notes)

@transaction.atomic
def cancel_sale(*, sale):
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == 'cancelled':
        raise ValueError('La venta ya fue anulada.')
    sale_movements = list(StockMovement.objects.filter(reference=f'SALE-{sale.pk}', movement_type='sale').select_related('product'))
    for movement in sale_movements:
        register_movement(product=movement.product, warehouse=sale.warehouse, movement_type='adjustment_in', quantity=movement.quantity, unit_cost=movement.unit_cost, reference=f'CANCEL-SALE-{sale.pk}', notes='Reintegro por anulación')
    sale.status = 'cancelled'
    sale.notes = f'{sale.notes}\nAnulada automáticamente.' if sale.notes else 'Anulada automáticamente.'
    sale.save(update_fields=['status', 'notes'])
    return sale

@transaction.atomic
def return_sale(*, sale, reason=''):
    sale = cancel_sale(sale=sale)
    sale.notes = f'{sale.notes}\nMotivo de devolución: {reason}' if reason else sale.notes
    sale.save(update_fields=['notes'])
    return sale

