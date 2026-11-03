from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('productos/', views.product_list, name='products'),
    path('productos/nuevo/', views.product_create, name='product_create'),
    path('movimientos/nuevo/', views.movement_create, name='movement_create'),
]
