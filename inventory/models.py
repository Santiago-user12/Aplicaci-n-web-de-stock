from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

class BusinessSettings(models.Model):
    name = models.CharField(max_length=120, default='Mi negocio')
    currency = models.CharField(max_length=3, default='ARS')
    industry_mode = models.CharField(max_length=30, default='retail')
    tax_mode = models.CharField(max_length=30, default='manual')
    dark_theme = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Warehouse(models.Model):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    address = models.CharField(max_length=240, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} ({self.code})'

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#635BFF')

    def __str__(self):
        return self.name

class Product(models.Model):
    COST_METHODS = [('weighted_average', 'Promedio ponderado'), ('fifo', 'FIFO'), ('last_cost', 'Último costo')]
    UNIT_TYPES = [('unit', 'Unidad'), ('weight', 'Peso'), ('volume', 'Volumen'), ('length', 'Longitud'), ('pack', 'Pack')]
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=50, blank=True, unique=True, null=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPES, default='unit')
    unit_label = models.CharField(max_length=20, default='unidad')
    cost_method = models.CharField(max_length=30, choices=COST_METHODS, default='weighted_average')
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    sale_price = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    min_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} [{self.sku}]'

    @property
    def margin(self):
        if not self.sale_price:
            return Decimal('0')
        return ((self.sale_price - self.cost) / self.sale_price * 100).quantize(Decimal('0.01'))

class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reserved = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['product', 'warehouse'], name='unique_product_warehouse')]

    @property
    def available(self):
        return self.quantity - self.reserved

class StockMovement(models.Model):
    TYPES = [('purchase', 'Compra'), ('sale', 'Venta'), ('adjustment_in', 'Ajuste de entrada'), ('adjustment_out', 'Ajuste de salida'), ('transfer', 'Transferencia'), ('production', 'Producción')]
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='movements')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    movement_type = models.CharField(max_length=20, choices=TYPES)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class Recipe(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='recipe')
    yield_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=1)

class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='items')
    ingredient = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)

    @property
    def cost(self):
        return self.quantity * self.ingredient.cost

class Customer(models.Model):
    name = models.CharField(max_length=160)
    tax_id = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name

class Sale(models.Model):
    STATUS = [('paid', 'Pagada'), ('pending', 'Pendiente'), ('cancelled', 'Anulada')]
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS, default='paid')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return sum((line.subtotal for line in self.items.all()), Decimal('0'))

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

class Supplier(models.Model):
    name = models.CharField(max_length=160)
    tax_id = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Purchase(models.Model):
    STATUS = [('received', 'Recibida'), ('pending', 'Pendiente'), ('cancelled', 'Anulada')]
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS, default='received')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return sum((line.subtotal for line in self.items.all()), Decimal('0'))

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2)

    @property
    def subtotal(self):
        return self.quantity * self.unit_cost

class UserProfile(models.Model):
    LANGUAGES = [('es', 'Español'), ('en', 'English')]
    ROLES = [('admin', 'Administrador'), ('manager', 'Encargado'), ('seller', 'Vendedor'), ('warehouse', 'Depósito'), ('viewer', 'Solo lectura')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    language = models.CharField(max_length=2, choices=LANGUAGES, default='es')
    role = models.CharField(max_length=20, choices=ROLES, default='viewer')

    def __str__(self):
        return f'{self.user.username} · {self.get_role_display()}'
