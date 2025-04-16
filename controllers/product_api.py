from odoo import http
from odoo.http import request
import json

# API Products
class ProductAPIController(http.Controller):

    @http.route('/api/product', auth='user', methods=['POST'], type='json', csrf=False)
    def create_product(self, **post):
        try:
            # Cargar los datos desde request.httprequest.data
            data = json.loads(request.httprequest.data)

            # Validar datos esenciales
            name = data.get('name')  # Solo el nombre es obligatorio
            if not name:
                return {"status": "error", "message": "Missing required field: name"}

            # Obtener otros campos (opcionales)
            sku = data.get('sku')
            sales_price = data.get('sales_price')
            description = data.get('description')

            # Verificar si el producto ya existe (solo si se proporciona SKU)
            if sku:
                product = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
                if product:
                    return {"status": "error", "message": f"Product with SKU {sku} already exists"}

            # Crear el producto
            new_product = request.env['product.product'].sudo().create({
                'default_code': sku,  # SKU es opcional
                'name': name,         # Nombre es obligatorio
                'list_price': float(sales_price) if sales_price else 0.0,  # Precio es opcional
                'description': description,  # Descripción es opcional
            })

            return {"status": "success", "message": "Product created successfully", "product_id": new_product.id}

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}

    @http.route('/api/product', auth='user', methods=['PUT'], type='json', csrf=False)
    def update_product(self, **post):
        try:
            # Cargar los datos desde request.httprequest.data
            data = json.loads(request.httprequest.data)

            # Validar datos esenciales
            sku = data.get('sku')
            name = data.get('name')
            sales_price = data.get('sales_price')
            description = data.get('description')

            if not sku:
                return {"status": "error", "message": "Missing required field: sku"}

            # Buscar el producto
            product = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
            if not product:
                return {"status": "error", "message": f"Product with SKU {sku} not found"}

            # Actualizar el producto
            update_vals = {}
            if name:
                update_vals['name'] = name
            if sales_price:
                update_vals['list_price'] = float(sales_price)
            if description:
                update_vals['description'] = description

            product.write(update_vals)

            return {"status": "success", "message": "Product updated successfully", "product_id": product.id}

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}

    @http.route('/api/product', auth='user', methods=['DELETE'], type='json', csrf=False)
    def delete_product(self, **post):
        try:
            # Cargar los datos desde request.httprequest.data
            data = json.loads(request.httprequest.data)

            # Validar datos esenciales
            sku = data.get('sku')

            if not sku:
                return {"status": "error", "message": "Missing required field: sku"}

            # Buscar el producto
            product = request.env['product.product'].sudo().search([('default_code', '=', sku)], limit=1)
            if not product:
                return {"status": "error", "message": f"Product with SKU {sku} not found"}

            # Eliminar el producto
            product.unlink()

            return {"status": "success", "message": "Product deleted successfully"}

        except Exception as e:
            return {"status": "error", "message": f"Error: {str(e)}"}