from odoo import http
from odoo.http import request
import json

class WooCommerceAPIController(http.Controller):

    @http.route('/api/woocommerce/order', auth='user', methods=['POST'], type='json', csrf=False)
    def receive_order(self, **post):
        try:
            # If type='json', post might already be parsed, but we keep this defensive parse.
            raw = request.httprequest.data
            data = json.loads(raw) if raw else (post or {})

            order_data = (data or {}).get('order', {})
            customer_data = order_data.get('customer', {}) or {}
            products_data = order_data.get('products', []) or []
            shipping_data = (order_data.get('shipping', {}) or {}).get('address', {}) or {}
            metadata = order_data.get('metadata', {}) or {}

            # installments (quote) - normalize to the string keys used by your PALIER dict
            installments_in = order_data.get('quote', '24')
            installments = str(installments_in or '24')
            if installments not in {'12', '24', '36', '48', '60'}:
                installments = '24'  # default safe fallback

            # price_quote from metadata (manual override per month)

            discount = metadata.get('price_discount', 0.0) or 0.0
            try:
                manual_quote = float(metadata.get('price_quote', 0.0)) if metadata.get('price_quote') not in (None, '') else 0.0
            except (TypeError, ValueError):
                manual_quote = 0.0

            if not customer_data or not products_data:
                return {"status": "error", "message": "Missing required fields: customer or products"}

            # Find or create customer
            partner = request.env['res.partner'].sudo().search([('email', '=', customer_data.get('email'))], limit=1)
            if not partner:
                partner_vals = {
                    'name': customer_data.get('name') or 'Customer',
                    'email': customer_data.get('email') or '',
                    'siren': customer_data.get('siren', '') or '',
                }
                partner = request.env['res.partner'].sudo().create(partner_vals)

            # 1) Create the order first (installments set up-front)
            sale_order_vals = {
                'partner_id': partner.id,
                'note': metadata.get('order_note', '') or '',
                'installments': installments,   # critical: parent has value before lines
            }
            sale_order = request.env['sale.order'].sudo().create(sale_order_vals)

            # 2) Now create lines referencing the existing order
            for p in products_data:
                sku = (p or {}).get('sku')
                qty = (p or {}).get('quantity', 1) or 1

                if not sku:
                    return {"status": "error", "message": "One of the products is missing SKU"}

                odoo_product = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                if not odoo_product:
                    return {"status": "error", "message": f"Product with SKU {sku} not found"}

                line_vals = {
                    'order_id': sale_order.id,
                    'product_id': odoo_product.id,
                    'product_uom_qty': qty,
                    'price_unit': odoo_product.lst_price,
                    'price_quote': manual_quote if manual_quote > 0 else 0.0,
                    'display_price_quote': manual_quote if manual_quote > 0 else 0.0,
                    'discount_price': discount or 0.0
                }

                request.env['sale.order.line'].sudo().create(line_vals)

            # 3) Shipping partner (optional)
            if any(shipping_data.values()):
                country_name = (shipping_data.get('country') or '').strip()
                country_id = False
                if country_name:
                    country_id = request.env['res.country'].sudo().search([('name', '=', country_name)], limit=1).id or False

                shipping_partner = request.env['res.partner'].sudo().create({
                    'name': partner.name,
                    'street': shipping_data.get('street', '') or '',
                    'city': shipping_data.get('city', '') or '',
                    'zip': shipping_data.get('zip_code', '') or '',
                    'country_id': country_id,
                    'type': 'delivery',
                    'parent_id': partner.id,
                })
                sale_order.sudo().write({'partner_shipping_id': shipping_partner.id})

            # (Optional) Force ORM to flush and ensure computes stored on lines are finalized
            sale_order.flush()
            sale_order.invalidate_cache()

            return {
                "status": "success",
                "message": "Order created successfully",
                "order_id": sale_order.id,
                "order_name": sale_order.name,
                "installments": installments,
            }

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}