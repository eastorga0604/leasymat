# __manifest__.py
{
    'name': 'Custom WooCommerce API2',
    'version': '1.0',
    'category': 'Custom',
    'author': 'Tu Nombre',
    'description': 'Módulo para integrar WooCommerce con Odoo a través de una API personalizada.',
    'depends': ['base','sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/financing_agency_menu.xml',
        'views/account_move_views.xml',
    ],
    'controllers': [
        'controllers/main.py',
        'controllers/product_api.py',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
