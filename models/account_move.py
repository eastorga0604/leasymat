from odoo import fields, models, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    include_full_service_warranty = fields.Boolean(
        string="Include Full Service Warranty",
        help="Copied from the sales order line."
    )


class AccountMove(models.Model):
    _inherit = 'account.move'

    amount_vat_20 = fields.Monetary(string='IVA 20%', compute='_compute_iva_20')
    amount_total_incl_vat_20 = fields.Monetary(string='Total Incl. IVA', compute='_compute_iva_20')

    custom_display_number = fields.Char(string="Custom Invoice Number", readonly=True)

    def _compute_custom_display_number(self):
        for record in self:
            if not record.invoice_date:
                record.custom_display_number = ''
                continue

            date_str = record.invoice_date.strftime('%Y%m%d')
            domain = [
                ('move_type', '=', record.move_type),
                ('state', '=', 'posted'),
                ('invoice_date', '=', record.invoice_date),
            ]
            count = self.search_count(domain) + 1
            record.custom_display_number = f'{date_str}-{count:02d}'

    def action_post(self):
        res = super().action_post()
        for move in self:
            if not move.custom_display_number:
                move._compute_custom_display_number()
        return res

    @api.depends('amount_total')
    def _compute_iva_20(self):
        for move in self:
            move.amount_vat_20 = move.currency_id.round(move.amount_total * 0.2)
            move.amount_total_incl_vat_20 = move.currency_id.round(move.amount_total * 1.2)