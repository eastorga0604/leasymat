# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta
from odoo.tools.float_utils import float_round
from babel.numbers import format_currency
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    installments = fields.Selection(
        [('24', '24'), ('36', '36'), ('48', '48'), ('60', '60')],
        string="Quotas",
        default='24',
        help="Number of quotas for payment."
    )

    financing_duration = fields.Integer(string='Financing Duration (Months)')
    financing_start_date = fields.Date(string='Start Date')
    financing_end_date = fields.Date(
        string='End Date', compute='_compute_financing_end_date', store=True
    )

    financing_agency_id = fields.Many2one(
        'financing.agency', string="Financing Agency", ondelete='set null'
    )

    warranty_start_date = fields.Date(
        string='Warranty Start Date', compute='_compute_warranty_dates', store=True
    )
    warranty_end_date = fields.Date(
        string='Warranty End Date', compute='_compute_warranty_dates', store=True
    )

    full_service_warranty_percentage = fields.Float(
        string="Full Service Warranty Percentage", default=10.0
    )
    transport = fields.Float(string="Transport", default=0.0)

    margin_amount = fields.Monetary(
        string="Margin (€)", compute="_compute_margin", store=True
    )
    margin_percent = fields.Float(
        string="Margin (%)", compute="_compute_margin", store=True
    )

    amount_untaxed = fields.Monetary(
        string='Untaxed Amount', compute='_amount_all', store=True, readonly=True
    )
    amount_tax = fields.Monetary(
        string='Taxes', compute='_amount_all', store=True, readonly=True
    )
    amount_total = fields.Monetary(
        string='Total', compute='_amount_all', store=True, readonly=True
    )

    # Optional helper for UI refresh (can keep or remove)
    display_amount_total = fields.Monetary(
        string='Display Total', store=True, readonly=False,
        help="Duplicated total used to force UI refresh when computed fields don't update."
    )

    amount_vat_20 = fields.Monetary(
        string="IVA (20%)",
        compute="_compute_vat_20",
        store=True,
        currency_field='currency_id'
    )
    amount_total_incl_vat_20 = fields.Monetary(
        string="Total Incl. IVA",
        compute="_compute_vat_20",
        store=True,
        currency_field='currency_id'
    )

    amount_total_sans_tva = fields.Monetary(
        string='TOTAL (Sans TVA)',
        currency_field='currency_id',
        compute='_compute_amount_total_sans_tva',
        store=True
    )

    list_price_total = fields.Monetary(
        string='List Price Total',
        currency_field='currency_id',
        compute='_compute_list_price_total',
        store=True
    )

    # ---------- COMPUTES (ORDER LEVEL) ----------

    @api.depends('installments', 'order_line.effective_price_quote', 'order_line.product_uom_qty')
    def _compute_amount_total_sans_tva(self):
        for order in self:
            months = int(order.installments or '1')
            total = 0.0
            for line in order.order_line:
                # TOTAL (Sans TVA) = monthly final * months (no taxes)
                total += (line.effective_price_quote or 0.0) * months
            order.amount_total_sans_tva = total

    @api.depends('order_line.product_id', 'order_line.product_uom_qty')
    def _compute_list_price_total(self):
        for order in self:
            order.list_price_total = sum(
                (l.product_id.list_price or 0.0) * (l.product_uom_qty or 0.0)
                for l in order.order_line
            )

    @api.depends('order_line.price_subtotal', 'order_line.product_id', 'installments')
    def _compute_margin(self):
        for order in self:
            # price_subtotal on the line is monthly (final) * qty
            monthly_total = sum(l.price_subtotal for l in order.order_line)
            months = int(order.installments or '1')
            full_quote = monthly_total * months
            total_cost = sum((l.product_id.lst_price or 0.0) for l in order.order_line)
            margin = full_quote - total_cost

            currency = order.currency_id
            order.margin_amount = float_round(margin, precision_rounding=currency.rounding)
            order.margin_percent = float_round((margin / total_cost) * 100, 2) if total_cost else 0.0

    @api.depends('amount_untaxed')
    def _compute_vat_20(self):
        for order in self:
            vat = order.amount_untaxed * 0.20
            total = order.amount_untaxed + vat
            order.amount_vat_20 = float_round(vat, precision_rounding=order.currency_id.rounding)
            order.amount_total_incl_vat_20 = float_round(total, precision_rounding=order.currency_id.rounding)

    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'transport')
    def _amount_all(self):
        for order in self:
            amount_untaxed = sum(l.price_subtotal for l in order.order_line)
            amount_tax = sum(l.price_tax for l in order.order_line)
            total = amount_untaxed + amount_tax + order.transport

            order.amount_untaxed = float_round(amount_untaxed, precision_rounding=order.currency_id.rounding)
            order.amount_tax = float_round(amount_tax, precision_rounding=order.currency_id.rounding)
            order.amount_total = float_round(total, precision_rounding=order.currency_id.rounding)
            order.display_amount_total = order.amount_total  # optional UI nudge

    @api.depends('date_order')
    def _compute_warranty_dates(self):
        for order in self:
            if order.date_order:
                order.warranty_start_date = order.date_order
                order.warranty_end_date = order.date_order + timedelta(days=365)
            else:
                order.warranty_start_date = False
                order.warranty_end_date = False

    @api.depends('financing_start_date', 'financing_duration')
    def _compute_financing_end_date(self):
        for order in self:
            if order.financing_start_date and order.financing_duration:
                order.financing_end_date = order.financing_start_date + timedelta(days=order.financing_duration * 30)
            else:
                order.financing_end_date = False

    # ---------- HOOKS ----------

    @api.onchange('installments')
    def _onchange_installments_clear_manual(self):
        """
        UI path: when user changes Quotas, clear manual on all in-form lines
        and snap the visible monthly back to the auto value immediately.
        """
        for order in self:
            for line in order.order_line:
                line.manual_price_quote = 0.0
                if line.price_quote:
                    line.display_price_quote = line.price_quote

    def write(self, vals):
        """
        Server/API path: clear manuals BEFORE updating installments so that
        recomputes (which depend on manual_price_quote & installments) run
        with manual=0 and produce the auto monthly.
        """
        if 'installments' in vals:
            self.mapped('order_line').write({'manual_price_quote': 0.0})
        return super().write(vals)

    @api.model
    def create(self, vals):
        return super().create(vals)

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        if self.financing_agency_id:
            invoice_vals['partner_id'] = self.financing_agency_id.id
            invoice_vals['narration'] = f"Customer financed: {self.partner_id.name}"
        return invoice_vals

    @api.depends('amount_untaxed', 'amount_tax', 'amount_total', 'transport')
    def _compute_tax_totals(self):
        super(SaleOrder, self)._compute_tax_totals()
        for order in self:
            if not order.tax_totals:
                continue
            tax_totals = order.tax_totals.copy()
            new_total = float_round(
                order.amount_untaxed + order.amount_tax + order.transport,
                precision_rounding=order.currency_id.rounding
            )
            tax_totals['amount_total'] = new_total
            tax_totals['amount_untaxed'] = float_round(
                order.amount_untaxed, precision_rounding=order.currency_id.rounding
            )
            tax_totals['formatted_amount_total'] = format_currency(new_total, 'EUR', locale='fr_FR')
            order.tax_totals = tax_totals