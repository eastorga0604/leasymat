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
        string="Auto Monthly Quote",
        compute="_compute_price_quote",
        store=False
    )

    display_price_quote = fields.Float(
        string="Auto Monthly Quote (Visible)",
        readonly=False
    )

    manual_price_quote = fields.Float(
        string="Manual Monthly Quote",
        help="Overrides the automatically calculated monthly quote if set."
    )

    include_full_service_warranty = fields.Boolean(
        string="Include Full Service Warranty",
        default=False
    )

    effective_price_quote = fields.Float(
        string="Monthly Quote (Final)",
        compute="_compute_effective_price_quote",
        store=False
    )

    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_price_subtotal_custom',
        store=True
    )


    # Create method
    @api.model
    def create(self, vals):
        manual = vals.get('manual_price_quote')
        auto = vals.get('display_price_quote') or vals.get('price_quote') or 0.0
        qty = vals.get('product_uom_qty') or 1.0
        currency = self.env.company.currency_id
        rounding = currency.rounding if currency else 0.01
        chosen_quote = manual if manual else auto
        subtotal = float_round(chosen_quote * qty, precision_rounding=rounding)
        vals['price_subtotal'] = subtotal
        return super().create(vals)


    # Compute the automatic calculated quote
    @api.depends('price_unit', 'include_full_service_warranty',
                 'order_id.full_service_warranty_percentage', 'order_id.installments')
    def _compute_price_quote(self):
        for line in self:
            total = (line.price_unit or 0.0) * 2.1
            months = line.env.context.get('installments') or line.order_id.installments or '24'

            if 500 <= total < 1500:
                palier = 'palier-500'
            elif 1500 <= total < 5000:
                palier = 'palier-1-500'
            elif 5000 <= total < 8000:
                palier = 'palier-5-000'
            elif 8000 <= total < 12000:
                palier = 'palier-8-000'
            elif 12000 <= total < 20000:
                palier = 'palier-12-000'
            elif 20000 <= total < 1000000:
                palier = 'palier-20-000'
            else:
                palier = 'palier-1-000-000'


            _logger.info(f"Computing price_quote for line {total} with palier {palier} and months {months}")

            try:
                coef = PALIER_COEFFICIENTS[palier][months]
                base_quote = (total * coef) / 100.0
                if line.include_full_service_warranty and line.order_id.full_service_warranty_percentage:
                    extra = base_quote * (line.order_id.full_service_warranty_percentage / 100.0)
                    base_quote += extra

                final = float_round(base_quote, precision_digits=2)
                line.price_quote = final
                line.display_price_quote = final

            except Exception as e:
                _logger.error(f"Error computing price_quote for line {line.id}: {e}")
                line.price_quote = 0.0
                line.display_price_quote = 0.0


    # Compute effective price quote
    @api.depends('manual_price_quote', 'price_quote', 'include_full_service_warranty',
                 'order_id.full_service_warranty_percentage')
    def _compute_effective_price_quote(self):
        for line in self:
            base = 0.0

            if line.manual_price_quote:
                base = line.manual_price_quote
            else:
                base = line.price_quote

            # Always apply warranty if checked
            if line.include_full_service_warranty and line.order_id.full_service_warranty_percentage:
                warranty_pct = line.order_id.full_service_warranty_percentage
                base += base * (warranty_pct / 100.0)

            line.effective_price_quote = float_round(base, precision_digits=2)


    # Compute amounts
    @api.depends('effective_price_quote', 'product_uom_qty', 'currency_id')
    def _compute_amount(self):
        for line in self:
            try:
                subtotal = float_round((line.effective_price_quote or 0.0) * line.product_uom_qty,
                                       precision_rounding=line.currency_id.rounding)
                line.price_subtotal = subtotal
                line.price_total = subtotal
            except Exception as e:
                _logger.error(f"[QUOTE] Error in _compute_amount for line {line.id}: {e}")
                line.price_subtotal = 0.0
                line.price_total = 0.0


    # Compute subtotal
    @api.depends('effective_price_quote', 'product_uom_qty', 'currency_id')
    def _compute_price_subtotal_custom(self):
        for line in self:
            try:
                subtotal = (line.effective_price_quote or 0.0) * line.product_uom_qty
                line.price_subtotal = float_round(subtotal, precision_rounding=line.currency_id.rounding)
                line.price_total = line.price_subtotal
            except Exception:
                line.price_subtotal = 0.0


    # Compute taxes
    @api.depends('effective_price_quote', 'product_uom_qty', 'tax_id')
    def _compute_tax_id(self):
        for line in self:
            taxes = line.tax_id.compute_all(
                line.effective_price_quote,
                currency=line.order_id.currency_id,
                quantity=line.product_uom_qty,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id
            )
            line.price_tax = float_round(taxes['total_included'] - taxes['total_excluded'],
                                         precision_rounding=line.currency_id.rounding)


    # Onchange for manual editing: clear warranty
    @api.onchange('manual_price_quote')
    def _onchange_manual_quote(self):
        for line in self:
            if line.manual_price_quote:
                line.include_full_service_warranty = False


    # Onchange qty or quote
    @api.onchange('product_uom_qty', 'display_price_quote')
    def _onchange_qty_or_quote(self):
        self._compute_effective_price_quote()
        self._compute_price_subtotal_custom()
        self._compute_amount()


    @api.onchange('order_id.installments', 'product_uom_qty')
    def _onchange_trigger_quote_recalc(self):
        installments = self.order_id.installments or '24'
        self.with_context(installments=installments)._compute_price_quote()
        self._compute_effective_price_quote()
        self._compute_price_subtotal_custom()
        self._compute_amount()


    @api.onchange('include_full_service_warranty', 'order_id.full_service_warranty_percentage')
    def _onchange_warranty_toggle(self):
        for line in self:
            if not line.manual_price_quote:
                line._compute_price_quote()
                line._compute_effective_price_quote()
                line._compute_price_subtotal_custom()
                line._compute_amount()

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'include_full_service_warranty': self.include_full_service_warranty,
            'price_unit': self.effective_price_quote,
            'tax_ids': [(6, 0, [])],  # Remove taxes
        })
        return res