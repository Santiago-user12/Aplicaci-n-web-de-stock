# StockPilot

Sistema web de control de stock, costos y operaciones para comercios, gastronomía, depósitos y sucursales.

## Stack

- Python 3.12+ / Django 5
- MySQL 8 (SQLite para desarrollo rápido)
- HTML/CSS responsive con tema oscuro
- pytest + pytest-django

## Funcionalidades actuales

- Dashboard operativo con valor de inventario y alertas de stock bajo.
- Catálogo de productos con SKU, unidad, costo, precio, margen y método de costo configurable.
- Múltiples depósitos y sucursales.
- Movimientos de entrada, salida, compra, venta, producción y ajustes.
- Promedio ponderado funcionando; FIFO y último costo quedan modelados para el siguiente incremento.
- Recetas y materias primas para gastronomía, con costo de receta.
- Punto de venta inicial con múltiples líneas, actualización de stock y cálculo del total.
- Compras a proveedores con actualización automática del costo y stock.
- Transferencias de stock entre depósitos con trazabilidad de movimientos.
- Descuento automático de ingredientes al vender un producto con receta.
- Historial de ventas con anulaciones y devoluciones que reintegran el stock.
- Reporte de ventas con ingresos, costos y utilidad bruta.
- Exportación de productos a CSV con stock total y margen.
- Comandas imprimibles desde el navegador, incluyendo notas para despacho.
- Clientes y proveedores básicos asociados a operaciones.
- Preferencia de idioma por usuario: Español o English, persistida en su perfil.
- Roles base configurables desde administración y permisos reales por operación:
  - administrador y encargado: gestión completa;
  - vendedor: ventas;
  - depósito: movimientos y transferencias;
  - solo lectura: consulta del dashboard y catálogo.
- Pantalla de acceso restringido para operaciones no autorizadas.
- Selector de idioma visible en el panel principal.
- Recuperación de contraseña por correo desde la pantalla de login; en desarrollo usa consola y en producción se configura SMTP mediante variables de entorno.
- Administración Django para proveedores, clientes, perfiles, recetas, depósitos, categorías y usuarios.
- Docker Compose con MySQL 8.4.

## Inicio local

```bash
python -m venv .venv
.venv/Scripts/activate       # Windows
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/`. Crear al menos un depósito desde `/admin/` antes de registrar movimientos.

Para habilitar el envío real de correos, configurá en `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.tu-proveedor.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu-cuenta
EMAIL_HOST_PASSWORD=tu-clave
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=no-reply@tudominio.com
```

## Con MySQL mediante Docker

```bash
docker compose up --build
```

La aplicación queda en `http://127.0.0.1:8000/`. Es una base preparada para red local: publicar el puerto 8000 en la IP del equipo servidor y acceder desde las demás PCs.

## Pruebas

```bash
pytest -q
```

## Próximos incrementos

AFIP, cuentas corrientes, traducción completa de formularios y reportes, importación masiva desde Excel, reportes por período y configuración visual desde la interfaz.
