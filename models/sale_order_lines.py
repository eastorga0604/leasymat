from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)

PALIER_COEFFICIENTS = {
    "palier-500": { "12": 9.571, "24": 5.171, "36": 3.710, "48": 2.742, "60": 2.235 },
    "palier-1-500": { "12": 9.248, "24": 5.127, "36": 3.474, "48": 2.703, "60": 2.186 },
    "palier-5-000": { "12": 9.168, "24": 5.081, "36": 3.429, "48": 2.694, "60": 2.163 },
    "palier-8-000": { "12": 9.087, "24": 4.992, "36": 3.383, "48": 2.646, "60": 2.139 },
    "palier-12-000": { "12": 9.048, "24": 4.860, "36": 3.337, "48": 2.599, "60": 2.114 },
    "palier-20-000": { "12": 9.008, "24": 4.816, "36": 3.293, "48": 2.576, "60": 2.100 },
    "palier-1-000-000": { "12": 9.008, "24": 4.816, "36": 3.293, "48": 2.576, "60": 2.100 },
}


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_quote = fields.Float(
        string="Monthly Quote",
        compute="_compute_price_quote",
        store=False
    )

    display_price_quote = fields.Float(
        string="Monthly Quote",
        readonly=False
    )

    include_full_service_warranty = fields.Boolean(
        string="Include Full Service Warranty",
        default=False
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_price_subtotal_custom',
        store=True
    )

    @api.model
    def create(self, vals):
        # Safety check: make sure needed fields exist
        price_quote = vals.get('display_price_quote') or vals.get('price_quote') or 0.0
        qty = vals.get('product_uom_qty') or 1.0

        # Fallback currency rounding
        currency = self.env.company.currency_id
        rounding = currency.rounding if currency else 0.01

        # Compute subtotal
        subtotal = float_round(price_quote * qty, precision_rounding=rounding)
        vals['price_subtotal'] = subtotal

        return super().create(vals)

    @api.depends('price_quote', 'product_uom_qty', 'currency_id')
    def _compute_amount(self):
        for line in self:
            try:
                subtotal = float_round((line.price_quote or 0.0) * line.product_uom_qty,
                                       precision_rounding=line.currency_id.rounding)
                line.price_subtotal = subtotal
                line.price_total = subtotal
            except Exception as e:
                _logger.error(f"[QUOTE] Error in _compute_amount for line {line.id}: {e}")
                line.price_subtotal = 0.0
                line.price_total = 0.0

    @api.depends('price_quote', 'currency_id', 'order_id.installments')
    def _compute_price_subtotal_custom(self):
        for line in self:
            try:
                #months = int(line.order_id.installments or 0)
                subtotal = (line.price_quote or 0.0) * line.product_uom_qty
                line.price_subtotal = float_round(subtotal, precision_rounding=line.currency_id.rounding)
                line.price_total = line.price_subtotal  # Assuming no tax is applied here

                _logger.info(
                    f"[QUOTE] Line {line.id} - Subtotal computed: {line.price_subtotal} for quantity {line.product_uom_qty} and price quote {line.price_quote}")
            except Exception:
                line.price_subtotal = 0.0

    @api.onchange('product_uom_qty', 'display_price_quote')
    def _onchange_qty_or_quote(self):
        self.price_quote = self.display_price_quote
        self._compute_price_subtotal_custom()
        self._compute_amount()

    @api.onchange('include_full_service_warranty', 'order_id.installments', 'product_uom_qty')
    def _onchange_trigger_quote_recalc(self):
        installments = self.order_id.installments or '24'
        self.with_context(installments=installments)._compute_price_quote()



    @api.depends('price_unit','include_full_service_warranty',
                 'order_id.full_service_warranty_percentage', 'order_id.installments')
    def _compute_price_quote(self):
        for line in self:
            total = (line.price_unit or 0.0) * 2.1
            months = self.env.context.get('installments') or line.order_id.installments or '24'

            _logger.info(f"[QUOTE] Line {line.id} - Order installments: {line.order_id.installments} - Used months: {months}")

            if total <= 500:
                palier = 'palier-500'
            elif total <= 1500:
                palier = 'palier-1-500'
            elif total <= 5000:
                palier = 'palier-5-000'
            elif total <= 8000:
                palier = 'palier-8-000'
            elif total <= 12000:
                palier = 'palier-12-000'
            elif total <= 20000:
                palier = 'palier-20-000'
            else:
                palier = 'palier-1-000-000'

            try:
                coef = PALIER_COEFFICIENTS[palier][months]
                base_quote = (total * coef) / 100.0

                warranty_extra = 0.0
                if line.include_full_service_warranty and line.order_id.full_service_warranty_percentage:
                    warranty_extra = base_quote * (line.order_id.full_service_warranty_percentage / 100.0)

                final_quote = float_round(base_quote + warranty_extra, precision_digits=2)
                line.price_quote = final_quote
                line.display_price_quote = final_quote

            except Exception as e:
                _logger.error(f"Error computing quote for line {line.id}: {e}")
                line.price_quote = 0.0
                line.display_price_quote = 0.0