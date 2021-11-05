from lxml.objectify import fromstring
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_edi_legend_ids = fields.Many2many(
        'l10n_mx_edi.fiscal.legend', string='Fiscal Legends', tracking=True,
        help="Legends under tax provisions, other than those contained in the Mexican CFDI standard.")

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id.l10n_mx_edi_legend_ids:
            self.l10n_mx_edi_legend_ids = self.partner_id.l10n_mx_edi_legend_ids
        return super()._onchange_partner_id()

    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        """If the CFDI was signed, try to adds the schemaLocation correctly"""
        result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
        if not cfdi_data:
            return result
        cfdi_data = cfdi_data.replace(b'xmlns__leyendasFisc', b'xmlns:leyendasFisc')
        cfdi = fromstring(cfdi_data)
        if 'leyendasFisc' not in cfdi.nsmap:
            return result
        cfdi.attrib['{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'] = '%s %s %s' % (
            cfdi.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'),
            'http://www.sat.gob.mx/leyendasFiscales',
            'http://www.sat.gob.mx/sitio_internet/cfd/leyendasFiscales/leyendasFisc.xsd')
        result['cfdi_node'] = cfdi
        return result

    @api.model
    def create(self, vals):
        if not vals.get('l10n_mx_edi_legend_ids') and vals.get('partner_id'):
            partner = self.env['res.partner'].browse(vals['partner_id'])
            vals.update({'l10n_mx_edi_legend_ids': [(6, 0, partner.l10n_mx_edi_legend_ids.ids)]})
        return super().create(vals)

    def _message_track(self, tracked_fields, initial):

        changes, tracking_value_ids = super()._message_track(tracked_fields, initial)
        for col_name, col_info in tracked_fields.items():
            if col_name not in ('l10n_mx_edi_legend_ids', ):
                continue

            initial_value = initial[col_name]
            new_value = self[col_name]

            if new_value != initial_value and (new_value or initial_value):
                tracking_sequence = getattr(self._fields[col_name], 'track_sequence', 100)

                initial_value = ", ".join(initial_value.mapped('display_name')) if initial_value else False
                new_value = ", ".join(new_value.mapped('display_name')) if new_value else False
                col_info['type'] = 'char'
                tracking = self.env['mail.tracking.value'].create_tracking_values(
                    initial_value, new_value, col_name, col_info, tracking_sequence, 'account.move')

                if tracking:
                    tracking_value_ids.append([0, 0, tracking])

                changes.add(col_name)

        return changes, tracking_value_ids
