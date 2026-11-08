from .models import BusinessSettings

def ui(request):
    english = getattr(request, 'LANGUAGE_CODE', 'es').startswith('en')
    business = BusinessSettings.objects.first()
    return {'LANGUAGE_CODE': 'en' if english else 'es', 'business': business, 'ui': {
        'summary': 'Overview' if english else 'Resumen',
        'products': 'Products' if english else 'Productos',
        'new_sale': 'New sale' if english else 'Nueva venta',
        'new_purchase': 'New purchase' if english else 'Nueva compra',
        'transfer': 'Transfer stock' if english else 'Transferir stock',
        'movement': 'Movement' if english else 'Movimiento',
        'admin': 'Administration' if english else 'Administración',
        'operations': 'OPERATIONS / INVENTORY' if english else 'OPERACIONES / INVENTARIO',
        'system_local': 'Local system' if english else 'Sistema local',
        'language': 'Language' if english else 'Idioma',
        'spanish': 'Español',
        'english': 'English',
        'logout': 'Log out' if english else 'Cerrar sesión',
    }}
