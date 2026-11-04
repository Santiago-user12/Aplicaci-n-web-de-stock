from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('productos/', views.product_list, name='products'),
    path('productos/nuevo/', views.product_create, name='product_create'),
    path('movimientos/nuevo/', views.movement_create, name='movement_create'),
    path('ventas/nueva/', views.sale_create, name='sale_create'),
    path('ventas/<int:sale_id>/comanda/', views.sale_receipt, name='sale_receipt'),
    path('ventas/', views.sale_list, name='sale_list'),
    path('ventas/<int:sale_id>/anular/', views.sale_cancel, name='sale_cancel'),
    path('ventas/<int:sale_id>/devolver/', views.sale_return, name='sale_return'),
    path('compras/nueva/', views.purchase_create, name='purchase_create'),
    path('transferencias/nueva/', views.transfer_create, name='transfer_create'),
    path('idioma/', views.set_language, name='set_language'),
]
