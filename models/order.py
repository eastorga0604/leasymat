# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)

PALIER_COEFFICIENTS = {
    "palier-500":       {"12": 9.571, "24": 5.171, "36": 3.710, "48": 2.742, "60": 2.235},
    "palier-1-500":     {"12": 9.248, "24": 5.127, "36": 3.474, "48": 2.703, "60": 2.186},
    "palier-5-000":     {"12": 9.168, "24": 5.081, "36": 3.429, "48": 2.694, "60": 2.163},
    "palier-8-000":     {"12": 9.087, "24": 4.992, "36": 3.383, "48": 2.646, "60": 2.139},
    "palier-12-000":    {"12": 9.048, "24": 4.860, "36": 3.337, "48": 2.599, "60": 2.114},
    "palier-20-000":    {"12": 9.008, "24": 4.816, "36": 3.293, "48": 2.576, "60": 2.100},
    "palier-1-000-000": {"12": 9.008, "24": 4.816, "36": 3.293, "48": 2.576, "60": 2.100},
}

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Auto monthly (computed from list price and palier)
    price_quote = fields.Float(
        string="Auto Monthly Quote",
        compute="_compute_price_quote",
        store=True
    )

    # UI-visible mirror; only synced from auto if no manual value
    display_price_quote = fields.Float(
        string="Auto Monthly Quote (Visible)",
        readonly=False
    )

    # Optional: user can type a manual monthly value in the UI
    manual_price_quote = fields.Float(
        string="Manual Monthly Quote",
        help="Overrides the automatically calculated monthly quote if set."
    )

    include_full_service_warranty = fields.Boolean(
        string="Include Full Service Warranty",
        default=False
    )

    # Final monthly after applying manual/auto + warranty
    effective_price_quote = fields.Float(
        string="Monthly Quote (Final)",
        compute="_compute_effective_price_quote",
        store=True
    )

    # Subtotal = monthly final * qty (stored)
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_price_subtotal_custom',
        store=True
    )

    discount_price = fields.Float(string='Discount (%)', default=0.0, store=True)

    # ---------- COMPUTES ----------

    @api.depends(
        'price_unit',
        'include_full_service_warranty',
        'order_id.full_service_warranty_percentage',
        'order_id.installments'
    )
    def _compute_price_quote(self):
        for line in self:
            total = (line.price_unit or 0.0) * 2.2
            months = int(line.order_id.installments or 24)

            rate = 0.05 / 12.0

            print(f"Computing price_quote for line {line.id}: price_unit={line.price_unit}, total={total}, months={months}")

            #if total < 1500:
            #    palier = 'palier-500'
            #elif 1500 <= total < 5000:
            #    palier = 'palier-1-500'
            #elif 5000 <= total < 8000:
            #    palier = 'palier-5-000'
            #elif 8000 <= total < 12000:
            #    palier = 'palier-8-000'
            #elif 12000 <= total < 20000:
            #    palier = 'palier-12-000'
            #elif 20000 <= total < 1000000:
            #    palier = 'palier-20-000'
            #else:
            #    palier = 'palier-1-000-000'

            try:
                #coef = PALIER_COEFFICIENTS[palier][months]
                #base_quote = (total * coef) / 100.0
                base_quote = (total + (total * rate * months)) / months;
                if line.include_full_service_warranty and line.order_id.full_service_warranty_percentage:
                    base_quote += base_quote * (line.order_id.full_service_warranty_percentage / 100.0)
                if line.discount_price and line.discount_price > 0.0:
                    discount_precent = line.discount_price / 100.0
                    discount_value = float_round(base_quote, precision_digits=2) * discount_precent
                    final = float_round(base_quote, precision_digits=2) - discount_value
                else:
                    final = float_round(base_quote, precision_digits=2)
                line.price_quote = final
                # Keep UI mirror in sync only if no manual override
                if not line.manual_price_quote:
                    line.display_price_quote = final
            except Exception as e:
                _logger.error(f"Error computing price_quote for line {line.id}: {e}")
                line.price_quote = 0.0
                if not line.manual_price_quote:
                    line.display_price_quote = 0.0

    @api.depends(
        'manual_price_quote',
        'price_quote',
        'include_full_service_warranty',
        'order_id.full_service_warranty_percentage',
        'order_id.installments'
    )
    def _compute_effective_price_quote(self):
        for line in self:
            # Manual wins if set (your chosen behavior)
            base = line.manual_price_quote or line.price_quote or 0.0
            if line.include_full_service_warranty and line.order_id.full_service_warranty_percentage:
                base += base * (line.order_id.full_service_warranty_percentage / 100.0)
            line.effective_price_quote = float_round(base, precision_digits=2)

    @api.depends('effective_price_quote', 'product_uom_qty', 'currency_id')
    def _compute_price_subtotal_custom(self):
        for line in self:
            subtotal = (line.effective_price_quote or 0.0) * (line.product_uom_qty or 0.0)
            line.price_subtotal = float_round(subtotal, precision_rounding=line.currency_id.rounding)
            # If you want price_total to mirror subtotal (no taxes here)
            line.price_total = line.price_subtotal

    @api.depends('effective_price_quote', 'product_uom_qty', 'tax_id')
    def _compute_tax_id(self):
        """Recompute taxes using the monthly final value as unit price."""
        for line in self:
            taxes = line.tax_id.compute_all(
                line.effective_price_quote or 0.0,
                currency=line.order_id.currency_id,
                quantity=line.product_uom_qty or 0.0,
                product=line.product_id,
                partner=line.order_id.partner_shipping_id
            )
            line.price_tax = float_round(
                taxes['total_included'] - taxes['total_excluded'],
                precision_rounding=line.currency_id.rounding
            )

    # ---------- ONCHANGES (that DO fire) ----------

    @api.onchange('manual_price_quote')
    def _onchange_manual_quote(self):
        for line in self:
            if line.manual_price_quote:
                line.include_full_service_warranty = False

    @api.onchange('product_uom_qty', 'display_price_quote')
    def _onchange_qty_or_quote(self):
        # Re-evaluate derived values when user edits qty or the visible quote
        self._compute_effective_price_quote()
        self._compute_price_subtotal_custom()

    @api.onchange('include_full_service_warranty', 'order_id.full_service_warranty_percentage')
    def _onchange_warranty_toggle(self):
        for line in self:
            if not line.manual_price_quote:
                line._compute_price_quote()
                line._compute_effective_price_quote()
                line._compute_price_subtotal_custom()

    # ---------- INVOICE MAPPING ----------

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        res.update({
            'include_full_service_warranty': self.include_full_service_warranty,
            # bill the total over the whole period: monthly final * installments
            #'price_unit': (self.effective_price_quote or 0.0) * int(self.order_id.installments or '24'),
            'price_unit': (self.product_id.list_price or 0.0) * 2.2,  # bill list price * 2.2
            'product_list_price': self.product_id.list_price or 0.0,
            'tax_ids': [(6, 0, [])],  # adjust to your tax policy
        })
        return res