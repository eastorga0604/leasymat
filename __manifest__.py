# __manifest__.py
{
    'name': 'Custom WooCommerce API2',
    'version': '1.0',
    'category': 'Custom',
    'author': 'Tu Nombre',
    'description': 'Módulo para integrar WooCommerce con Odoo a través de una API personalizada.',
    'depends': ['base','sale','crm', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/financing_agency_menu.xml',
        'views/account_move_views.xml',
        'views/crm_quick_create_patch.xml',
    ],
    'controllers': [
        'controllers/main.py',
        'controllers/product_api.py',
    ],
    'assets': {
        'web.assets_backend': [
            '/leasymat/static/src/js/kanban_quick_create_patch.js',  # <-- ADD THIS
            '/leasymat/static/src/css/custom_styles.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
