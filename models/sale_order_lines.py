from odoo import models, fields,api
from datetime import timedelta
import logging
from odoo.tools.float_utils import float_round

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
        store=True,
        help="Monthly payment amount for this product based on selected installments."
    )

    @api.depends('order_id.installments', 'price_unit')
    def _compute_price_quote(self):
        for line in self:
            total = (line.price_unit or 0.0) * 2.1  # Assuming a fixed factor of 2.1 for total calculation
            months = line.order_id.installments or '12'

            # Determine palier
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
                line.price_quote = float_round((total * coef) / 100.0, precision_digits=2)
            except Exception:
                line.price_quote = 0.0

        _logger.debug(f"Computed price_quote for line {line.id}: {line.price_quote} (total: {total}, months: {months}, palier: {palier})")