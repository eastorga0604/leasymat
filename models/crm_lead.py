from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)
class CrmLead(models.Model):
    _inherit = 'crm.lead'

    sale_order_id = fields.Many2one('sale.order', string="Linked Quotation", readonly=True)

    @api.model
    def create(self, vals):
        lead = super().create(vals)
        _logger.info(f"🔥 New lead created: {lead.name}")

        if lead.partner_id:
            sale_order = self.env['sale.order'].create({
                'partner_id': lead.partner_id.id,
                'opportunity_id': lead.id,
                'origin': f'Lead: {lead.name}',
            })
            lead.sale_order_id = sale_order.id
            _logger.info(f"✅ Quotation created: {sale_order.name}")

        return lead