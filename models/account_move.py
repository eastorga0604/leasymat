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

    @api.depends('amount_total')
    def _compute_iva_20(self):
        for move in self:
            move.amount_vat_20 = move.currency_id.round(move.amount_total * 0.2)
            move.amount_total_incl_vat_20 = move.currency_id.round(move.amount_total * 1.2)