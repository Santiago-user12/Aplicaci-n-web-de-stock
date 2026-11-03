from django.contrib import admin
from .models import BusinessSettings, Warehouse, Category, Product, Stock, StockMovement, Recipe, RecipeItem, Customer, Sale, SaleItem

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'category', 'cost', 'sale_price', 'margin', 'active')
    search_fields = ('sku', 'name', 'barcode')
    list_filter = ('active', 'unit_type', 'cost_method')

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity', 'reserved', 'available')
    list_filter = ('warehouse',)
    search_fields = ('product__name', 'product__sku')

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'movement_type', 'product', 'warehouse', 'quantity', 'unit_cost')
    list_filter = ('movement_type', 'warehouse')
    date_hierarchy = 'created_at'

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'warehouse', 'customer', 'status', 'total')
    list_filter = ('status', 'warehouse')
    date_hierarchy = 'created_at'

admin.site.register([BusinessSettings, Warehouse, Category, Recipe, RecipeItem, Customer, SaleItem])
