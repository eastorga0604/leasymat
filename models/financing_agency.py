from odoo import models, fields,api

class FinancingAgency(models.Model):
    _name = 'financing.agency'
    _description = 'Financing Agency'

    #name = fields.Char(string="Agency Name", required=True)
    #contact_info = fields.Text(string="Contact Information")
    #active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string="Name", required=True)  # Nombre del organismo
    description = fields.Text(string="Description")
    partner_id = fields.Many2one(
        'res.partner',
        string="Customer",
        required=True,
        help="Select the corresponding partner record for this financing agency."
    )

    @api.model
    def create(self, vals):
        if 'partner_id' not in vals:
            partner_vals = {
                'name': vals.get('name'),
                'is_company': True,
                'customer_rank': 1,  # Marca este contacto como cliente
            }
            partner = self.env['res.partner'].create(partner_vals)
            vals['partner_id'] = partner.id
        return super(FinancingAgency, self).create(vals)