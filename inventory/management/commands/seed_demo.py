from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import BusinessSettings, Category, Customer, PaymentMethod, Product, Recipe, RecipeItem, Supplier, Warehouse
from inventory.services import create_purchase, create_sale, record_customer_charge, record_customer_payment, record_supplier_invoice

class Command(BaseCommand):
    help = 'Carga un negocio demo coherente para portfolio y pruebas.'

    @transaction.atomic
    def handle(self, *args, **options):
        BusinessSettings.objects.update_or_create(pk=1, defaults={
            'name': 'La Esquina Multirubro', 'brand_name': 'La Esquina', 'currency': 'ARS',
            'industry_mode': 'retail_gastronomy', 'tax_mode': 'manual',
            'primary_color': '#7c6cff', 'secondary_color': '#45d49c', 'dark_theme': True,
        })
        categories = {name: Category.objects.get_or_create(name=name)[0] for name in ['Almacén', 'Bebidas', 'Gastronomía', 'Limpieza', 'Packaging']}
        warehouses = {}
        for name, code, address in [
            ('Depósito Central', 'CENTRAL', 'Av. San Martín 1200'),
            ('Cocina', 'COCINA', 'Av. San Martín 1200'),
            ('Salón', 'SALON', 'Av. San Martín 1200'),
            ('Sucursal Norte', 'NORTE', 'Calle 12 Nº 450'),
        ]:
            warehouses[code], _ = Warehouse.objects.update_or_create(code=code, defaults={'name': name, 'address': address, 'active': True})
        catalog = [
            ('HAR-25', 'Harina 000 x 25 kg', 'Almacén', 'pack', 'bolsa', 18000, 24000, 2),
            ('QUE-1', 'Queso mozzarella', 'Gastronomía', 'weight', 'kg', 8500, 13000, 8),
            ('SAL-1', 'Salsa de tomate', 'Gastronomía', 'volume', 'litro', 2200, 3500, 10),
            ('LEV-1', 'Levadura fresca', 'Gastronomía', 'weight', 'kg', 4200, 7000, 3),
            ('CAR-1', 'Carne picada premium', 'Gastronomía', 'weight', 'kg', 7500, 12000, 8),
            ('PAP-1', 'Papas prefritas x 5 kg', 'Gastronomía', 'pack', 'bolsa', 9000, 14500, 3),
            ('GAS-225', 'Gaseosa cola 2.25 L', 'Bebidas', 'unit', 'botella', 2300, 3800, 12),
            ('AGU-500', 'Agua mineral 500 ml', 'Bebidas', 'unit', 'botella', 700, 1200, 20),
            ('CER-1', 'Cerveza lata 473 ml', 'Bebidas', 'unit', 'lata', 1600, 2900, 18),
            ('CAF-500', 'Café molido 500 g', 'Almacén', 'unit', 'paquete', 4200, 7500, 6),
            ('ARR-1', 'Arroz largo fino 1 kg', 'Almacén', 'weight', 'kg', 1600, 2800, 10),
            ('FID-500', 'Fideos secos 500 g', 'Almacén', 'unit', 'paquete', 1200, 2200, 10),
            ('ACE-15', 'Aceite girasol 1.5 L', 'Almacén', 'volume', 'botella', 3200, 5200, 8),
            ('DET-750', 'Detergente 750 ml', 'Limpieza', 'volume', 'botella', 1800, 3200, 5),
            ('CAJ-20', 'Caja delivery x 20', 'Packaging', 'pack', 'pack', 6000, 9500, 4),
            ('PIZ-MUZ', 'Pizza muzzarella', 'Gastronomía', 'unit', 'unidad', 6500, 12500, 5),
            ('PIZ-NAP', 'Pizza napolitana', 'Gastronomía', 'unit', 'unidad', 7200, 14000, 5),
            ('HAM-COM', 'Hamburguesa completa', 'Gastronomía', 'unit', 'unidad', 5200, 11000, 5),
            ('PAP-RAC', 'Papas fritas ración', 'Gastronomía', 'unit', 'ración', 1800, 4500, 8),
        ]
        products = {}
        for sku, name, category, unit_type, unit_label, cost, price, minimum in catalog:
            products[sku], _ = Product.objects.update_or_create(sku=sku, defaults={
                'name': name, 'category': categories[category], 'unit_type': unit_type, 'unit_label': unit_label,
                'cost': Decimal(str(cost)), 'sale_price': Decimal(str(price)), 'min_stock': Decimal(str(minimum)), 'active': True,
            })
        recipes = {
            'PIZ-MUZ': [('HAR-25', Decimal('0.18')), ('QUE-1', Decimal('0.22')), ('SAL-1', Decimal('0.12')), ('LEV-1', Decimal('0.006'))],
            'PIZ-NAP': [('HAR-25', Decimal('0.18')), ('QUE-1', Decimal('0.18')), ('SAL-1', Decimal('0.12')), ('LEV-1', Decimal('0.006'))],
            'HAM-COM': [('CAR-1', Decimal('0.18')), ('PAP-1', Decimal('0.15'))],
            'PAP-RAC': [('PAP-1', Decimal('0.06'))],
        }
        for sku, ingredients in recipes.items():
            recipe, _ = Recipe.objects.update_or_create(product=products[sku], defaults={'yield_quantity': 1})
            recipe.items.all().delete()
            for ingredient_sku, quantity in ingredients:
                RecipeItem.objects.create(recipe=recipe, ingredient=products[ingredient_sku], quantity=quantity)
        suppliers = {name: Supplier.objects.get_or_create(name=name, defaults={'phone': phone})[0] for name, phone in [('Distribuidora Norte', '11-4444-1000'), ('Frigorífico La Pampa', '11-4444-2000'), ('Bebidas del Sur', '11-4444-3000')]}
        customers = {name: Customer.objects.get_or_create(name=name, defaults={'phone': phone})[0] for name, phone in [('Martín Gómez', '11-5555-1000'), ('Comedor El Sol', '11-5555-2000'), ('Ana López', '11-5555-3000')]}
        payments = {name: PaymentMethod.objects.get_or_create(name=name, defaults={'active': True, 'sort_order': i})[0] for i, name in enumerate(['Efectivo', 'Tarjeta de débito', 'Tarjeta de crédito', 'Transferencia bancaria', 'Mercado Pago', 'Cuenta corriente'])}
        create_purchase(supplier=suppliers['Distribuidora Norte'], warehouse=warehouses['CENTRAL'], lines=[(products['CAF-500'], 20, 4200), (products['ARR-1'], 40, 1600), (products['FID-500'], 40, 1200), (products['ACE-15'], 30, 3200), (products['DET-750'], 20, 1800), (products['CAJ-20'], 10, 6000)])
        create_purchase(supplier=suppliers['Frigorífico La Pampa'], warehouse=warehouses['COCINA'], lines=[(products['CAR-1'], 20, 7500), (products['QUE-1'], 20, 8500), (products['HAR-25'], 10, 18000), (products['SAL-1'], 25, 2200), (products['LEV-1'], 5, 4200), (products['PAP-1'], 12, 9000)])
        create_purchase(supplier=suppliers['Bebidas del Sur'], warehouse=warehouses['SALON'], lines=[(products['GAS-225'], 40, 2300), (products['AGU-500'], 60, 700), (products['CER-1'], 48, 1600)])
        create_purchase(supplier=suppliers['Distribuidora Norte'], warehouse=warehouses['NORTE'], lines=[(products['CAF-500'], 8, 4200), (products['ARR-1'], 15, 1600), (products['ACE-15'], 10, 3200), (products['GAS-225'], 12, 2300)])
        create_purchase(supplier=suppliers['Distribuidora Norte'], warehouse=warehouses['COCINA'], lines=[(products['PIZ-MUZ'], 12, 6500), (products['PIZ-NAP'], 10, 7200), (products['HAM-COM'], 10, 5200), (products['PAP-RAC'], 20, 1800)])
        create_sale(warehouse=warehouses['SALON'], customer=customers['Ana López'], payment_method=payments['Tarjeta de débito'], lines=[(products['GAS-225'], 2, 'Bien frías'), (products['CER-1'], 2, 'Sin vaso')])
        create_sale(warehouse=warehouses['COCINA'], customer=customers['Martín Gómez'], payment_method=payments['Mercado Pago'], consume_recipe=True, lines=[(products['PIZ-MUZ'], 2, 'Cortar en 8 porciones'), (products['PAP-RAC'], 1, 'Extra ketchup')], notes='Retira por mostrador')
        create_sale(warehouse=warehouses['COCINA'], customer=customers['Comedor El Sol'], payment_method=payments['Cuenta corriente'], consume_recipe=True, lines=[(products['HAM-COM'], 3, 'Sin pepinillos')], notes='Pedido semanal')
        record_customer_charge(customer=customers['Comedor El Sol'], amount=Decimal('33000'), note='Pedido semanal a cuenta corriente')
        record_customer_payment(customer=customers['Comedor El Sol'], amount=Decimal('10000'), note='Seña')
        record_supplier_invoice(supplier=suppliers['Frigorífico La Pampa'], amount=Decimal('40000'), note='Factura demo pendiente')
        self.stdout.write(self.style.SUCCESS('Demo creada: La Esquina Multirubro'))
        self.stdout.write('Depósitos: 4 | Productos: %s | Recetas: %s | Compras: 5 | Ventas: 3' % (len(products), len(recipes)))
