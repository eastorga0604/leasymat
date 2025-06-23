from odoo import http
from odoo.http import request
import json

class WooCommerceAPIController(http.Controller):

    @http.route('/api/woocommerce/order', auth='user', methods=['POST'], type='json', csrf=False)
    def receive_order(self, **post):
        try:
            # Cargar los datos desde request.httprequest.data
            data = json.loads(request.httprequest.data)

            # Validar datos esenciales
            order_data = data.get('order', {})
            customer_data = order_data.get('customer', {})
            products_data = order_data.get('products', [])
            shipping_data = order_data.get('shipping', {}).get('address', {})
            installments = order_data.get('quote', 0)

            metadata = order_data.get('metadata', {})

            price_quote = metadata.get('price_quote', 0.0)

            if not customer_data or not products_data:
                return {"status": "error", "message": "Missing required fields: customer or products"}

            # Buscar o crear cliente
            partner = request.env['res.partner'].sudo().search([('email', '=', customer_data.get('email'))], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': customer_data.get('name'),
                    'email': customer_data.get('email'),
                })

            # Crear líneas de la orden
            order_lines = []
            for product in products_data:
                odoo_product = request.env['product.product'].sudo().search([('default_code', '=', product.get('sku'))], limit=1)
                if not odoo_product:
                    return {"status": "error", "message": f"Product with SKU {product.get('sku')} not found"}

                order_lines.append((0, 0, {
                    'product_id': odoo_product.id,
                    'product_uom_qty': product.get('quantity', 1),
                    'price_unit': odoo_product.lst_price,
                    'price_quote': price_quote
                }))

            # Crear la orden de venta
            sale_order = request.env['sale.order'].sudo().create({
                'partner_id': partner.id,
                'order_line': order_lines,
                'note': metadata.get('order_note', ''),
                'installments': installments
            })

            # Agregar dirección de envío si aplica
            if shipping_data:
                shipping_partner = request.env['res.partner'].sudo().create({
                    'name': partner.name,
                    'street': shipping_data.get('street', ''),
                    'city': shipping_data.get('city', ''),
                    'zip': shipping_data.get('zip_code', ''),
                    'country_id': request.env['res.country'].sudo().search([('name', '=', shipping_data.get('country', ''))], limit=1).id,
                })
                sale_order.partner_shipping_id = shipping_partner.id

            return {"status": "success", "message": "Order created successfully", "order_id": sale_order.id}

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}
