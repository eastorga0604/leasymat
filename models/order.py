from odoo import models, fields,api
from datetime import timedelta
import logging
from odoo.tools.float_utils import float_round


_logger = logging.getLogger(__name__)



class SaleOrder(models.Model):
    _inherit = 'sale.order'

    #payment_method = fields.Char(string="WooCommerce Payment Method")
    #installments = fields.Integer(string="Quota",required=False,readonly=False, help="Number of quota the customer will pay for this order",
    #                              default=1)
    installments = fields.Selection(
        selection=[
            ('12', '12'),
            ('24', '24'),
            ('48', '48'),
            ('60', '60'),

        ],
        string="Quotas",
        required=False,
        readonly=False,
        help="Number of quotas in which the customer will pay for this order.",
        default='12'
    )
    financing_duration = fields.Integer(
        string='Financing Duration (Months)',
        help='Duration of the financing contract in months.'
    )
    financing_start_date = fields.Date(
        string='Start Date',
        help='Start date of the financing contract.'
    )
    financing_end_date = fields.Date(
        string='End Date',
        compute='_compute_financing_end_date',
        store=True,
        help='End date of the financing contract, calculated based on the start date and duration.'
    )
    financing_agency_id = fields.Many2one(
        'financing.agency',  # Relación con el modelo que creaste
        string="Financing Agency",  # Nombre que verá el usuario
        help="Select the financing agency for this sales order",  # Ayuda para el campo
        ondelete='set null'  # Si se elimina un organismo, este campo queda vacío
    )

    include_standard_warranty = fields.Boolean(
        string="Include Standard Warranty",
        default=True,
        help="Indicates if the standard warranty is included in this sale."
    )
    warranty_start_date = fields.Date(
        string='Warranty Start Date',
        compute='_compute_warranty_dates',
        store=True,
        help='Start date of the standard warranty.'
    )
    warranty_end_date = fields.Date(
        string='Warranty End Date',
        compute='_compute_warranty_dates',
        store=True,
        help='End date of the standard warranty (1 year from the start date).'
    )
    include_full_service_warranty = fields.Boolean(
        string="Include Full Service Warranty",
        default=False,
        help="Indicates if the Full Service warranty is selected for this sale."
    )
    full_service_warranty_percentage = fields.Float(
        string="Full Service Warranty Percentage", 
        default=10.0, 
        help="The percentage used to calculate the Full Service Warranty cost."
    )
    full_service_warranty_cost = fields.Monetary(
        string="Full Service Warranty Cost", 
        compute="_compute_full_service_warranty_cost", 
        store=True
    )
    amount_total_with_warranty = fields.Monetary(
        string="Total with Warranty",
        compute="_compute_amount_total_with_warranty",
        store=True,
        help="Total amount including the Full Service Warranty cost."
    )

    transport = fields.Float(string="Transport",
                             help="Transport cost for the order.",
                             default=0.0)

    margin_amount = fields.Monetary(
        string="Margin (€)",
        compute="_compute_margin",
        store=True,
        help="Total margin in currency."
    )

    margin_percent = fields.Float(
        string="Margin (%)",
        compute="_compute_margin",
        store=True,
        help="Margin as a percentage of untaxed amount."
    )

    @api.depends('order_line.price_quote', 'amount_total_with_warranty')
    def _compute_margin(self):
        for order in self:
            total_sales = order.amount_total_with_warranty or 0.0
            total_cost = sum(line.price_quote for line in order.order_line if line.price_quote) or 0.0
            currency = order.currency_id

            margin = total_sales - total_cost
            order.margin_amount = float_round(margin, precision_rounding=currency.rounding)
            order.margin_percent = (
                float_round((margin / total_sales) * 100, 2)
                if total_sales else 0.0
            )

    @api.depends('order_line.price_total', 'transport')
    def _amount_all(self):
        """
        Override the default computation to include the transport value.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax

            order.amount_untaxed = amount_untaxed
            order.amount_tax = amount_tax

            # Include transport in total
            order.amount_total = float_round(
                amount_untaxed + amount_tax + order.transport,
                precision_rounding=order.currency_id.rounding
            )
    @api.onchange('include_standard_warranty')
    def _onchange_include_standard_warranty(self):
        if self.include_standard_warranty:
            self.include_full_service_warranty = False

    @api.onchange('include_full_service_warranty')
    def _onchange_include_full_service_warranty(self):
        if self.include_full_service_warranty:
            self.include_standard_warranty = False
    
    @api.depends('amount_total', 'full_service_warranty_cost')
    def _compute_amount_total_with_warranty(self):
        for order in self:
            order.amount_total_with_warranty = order.amount_total + order.full_service_warranty_cost
    @api.depends('include_full_service_warranty', 'amount_total', 'full_service_warranty_percentage')
    def _compute_full_service_warranty_cost(self):
        for order in self:
            if order.include_full_service_warranty and order.full_service_warranty_percentage:
                # Calcular sobre el monto total con impuestos
                order.full_service_warranty_cost = (order.amount_untaxed * order.full_service_warranty_percentage) / 100
            else:
                order.full_service_warranty_cost = 0.0
    @api.depends('date_order')
    def _compute_warranty_dates(self):
        """Calculate warranty start and end dates based on confirmation date."""
        for order in self:
            if order.date_order:
                order.warranty_start_date = order.date_order
                order.warranty_end_date = order.date_order + timedelta(days=365)
            else:
                order.warranty_start_date = False
                order.warranty_end_date = False

    def create(self, vals):
        """Add standard warranty product automatically to new sales orders."""
        order = super(SaleOrder, self).create(vals)
        if order.include_standard_warranty: # pylint: disable=no-member
            warranty_product = self.env['product.product'].search([('name', '=', 'Garantía Estándar')], limit=1)
            if warranty_product:
                order.order_line.create({ # pylint: disable=no-member
                    'order_id': order.id, # pylint: disable=no-member
                    'product_id': warranty_product.id,
                    'product_uom_qty': 1,
                    'price_unit': 0.0,  # Costo estándar (sin cargo adicional)
                })
        return order
    
    @api.depends('financing_start_date', 'financing_duration')
    def _compute_financing_end_date(self):
        for order in self:
            if order.financing_start_date and order.financing_duration:
                order.financing_end_date = order.financing_start_date + timedelta(days=order.financing_duration * 30)
            else:
                order.financing_end_date = False
    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice() # pylint: disable=no-member

        # Personalizar la factura
        if self.financing_agency_id:
            # Cambiar el cliente de la factura al organismo de financiación
            invoice_vals['partner_id'] = self.financing_agency_id.id
            invoice_vals['narration'] = f"Customer financed: {self.partner_id.name}" # pylint: disable=no-member
            
        return invoice_vals
    
    def _create_invoices(self, grouped=False, final=False):
        invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final) # pylint: disable=no-member
        
        for order in self:
            for invoice in invoices:
                if order.full_service_warranty_cost:
                    # Buscar el producto de garantía de servicio completo
                    warranty_product = self.env['product.product'].search(
                        [('name', '=', 'Full Service Warranty')], limit=1)
                    
                    if warranty_product:
                        # Crear la línea de factura para la garantía de servicio completo
                        self.env['account.move.line'].create({
                            'move_id': invoice.id,
                            'product_id': warranty_product.id,
                            'name': warranty_product.name,
                            'quantity': 1,
                            'price_unit': order.full_service_warranty_cost,
                            'tax_ids': [(5, 0, 0)],  # Sin impuestos
                            'account_id': warranty_product.property_account_income_id.id or warranty_product.categ_id.property_account_income_categ_id.id,
                        })
                
                if order.financing_agency_id:
                    # Cambiar el cliente de la factura al organismo de financiación
                    invoice.partner_id = order.financing_agency_id.partner_id.id
                    if order.partner_id:
                        invoice.narration = f"{order.partner_id.name}"
                        _logger.info(f"Narration asignada en _create_invoices: {invoice.narration}")
                    else:
                        _logger.warning("No partner_id found for this sale order.")
        
        return invoices
