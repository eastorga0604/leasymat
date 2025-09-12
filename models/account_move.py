from odoo import fields, models, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    include_full_service_warranty = fields.Boolean(
        string="Include Full Service Warranty",
        help="Copied from the sales order line."
    )

    product_list_price = fields.Float(
        string="Product List Price",
        related='product_id.list_price',
        store=False,  # or True if you want it persisted and searchable
        readonly=True
    )

class AccountMove(models.Model):
    _inherit = 'account.move'

    amount_vat_20 = fields.Monetary(string='IVA 20%', compute='_compute_iva_20')
    amount_total_incl_vat_20 = fields.Monetary(string='Total Incl. IVA', compute='_compute_iva_20')

    custom_display_number = fields.Char(string="Custom Invoice Number", readonly=True)

    financing_agency_id = fields.Many2one(
        'financing.agency',
        string="Financing Agency",
        ondelete='set null'
    )

    invoice_title = fields.Char(string="Invoice Title", help="Custom title for the invoice.", default="Facture")

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

    @api.depends('amount_total', 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity')
    def _compute_iva_20(self):
        for move in self:
            total = sum(line.price_subtotal for line in move.invoice_line_ids)
            move.amount_vat_20 = move.currency_id.round(total * 0.2)
            move.amount_total_incl_vat_20 = move.currency_id.round(total * 1.2)

    @api.onchange('invoice_line_ids')
    def _onchange_recompute_iva_20(self):
        self._compute_iva_20()

    @api.onchange('financing_agency_id')
    def _onchange_financing_agency(self):
        if self.financing_agency_id:
            self.partner_id = self.financing_agency_id.partner_id

    @api.model
    def create(self, vals):
        """Ensure partner_id is set when financing_agency_id is provided."""
        if vals.get('financing_agency_id') and not vals.get('partner_id'):
            agency = self.env['financing.agency'].browse(vals['financing_agency_id'])
            vals['partner_id'] = agency.partner_id.id
        return super(AccountMove, self).create(vals)

    def write(self, vals):
        """Ensure partner_id updates if financing_agency_id changes."""
        res = super(AccountMove, self).write(vals)
        if 'financing_agency_id' in vals:
            for record in self:
                if record.financing_agency_id:
                    record.partner_id = record.financing_agency_id.partner_id
        return res