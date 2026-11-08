import csv
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from django.db import transaction
from openpyxl import load_workbook
from .models import Category, Product, Warehouse
from .services import register_movement

@transaction.atomic
def import_products_csv(csv_text):
    reader = csv.DictReader(StringIO(csv_text.lstrip('\ufeff')))
    result = {'created': 0, 'updated': 0, 'stock_rows': 0, 'errors': []}
    required = {'SKU', 'Producto', 'Costo', 'Precio venta'}
    if not required.issubset(set(reader.fieldnames or [])):
        return {**result, 'errors': ['Faltan columnas obligatorias: SKU, Producto, Costo, Precio venta']}
    for row_number, row in enumerate(reader, start=2):
        try:
            sku = row.get('SKU', '').strip()
            name = row.get('Producto', '').strip()
            if not sku or not name:
                raise ValueError('SKU y Producto son obligatorios')
            cost = Decimal(row.get('Costo', '0').strip() or '0')
            sale_price = Decimal(row.get('Precio venta', '0').strip() or '0')
            category = None
            if row.get('Categoría', '').strip():
                category, _ = Category.objects.get_or_create(name=row['Categoría'].strip())
            product, created = Product.objects.update_or_create(sku=sku, defaults={'name': name, 'category': category, 'cost': cost, 'sale_price': sale_price})
            result['created' if created else 'updated'] += 1
            quantity = Decimal(row.get('Stock', '0').strip() or '0')
            warehouse_code = row.get('Depósito', '').strip()
            if quantity > 0 and warehouse_code:
                warehouse = Warehouse.objects.get(code=warehouse_code)
                register_movement(product=product, warehouse=warehouse, movement_type='adjustment_in', quantity=quantity, unit_cost=cost, reference='CSV-IMPORT')
                result['stock_rows'] += 1
        except (InvalidOperation, ValueError, Warehouse.DoesNotExist) as error:
            result['errors'].append(f'Fila {row_number}: {error}')
    return result

def import_products_xlsx(file_bytes):
    workbook = load_workbook(filename=BytesIO(file_bytes), read_only=True, data_only=True)
    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return {'created': 0, 'updated': 0, 'stock_rows': 0, 'errors': ['El archivo está vacío.']}
    output = StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(['' if value is None else value for value in row])
    return import_products_csv(output.getvalue())
