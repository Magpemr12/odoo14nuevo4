from lxml.objectify import fromstring
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        """If the CFDI was signed, try to adds the schemaLocation correctly"""
        result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
        if not cfdi_data:
            return result
        cfdi_data = cfdi_data.replace(b'xmlns__terceros', b'xmlns:terceros')
        cfdi = fromstring(cfdi_data)
        if 'terceros' not in cfdi.nsmap:
            return result
        cfdi.attrib['{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'] = '%s %s %s' % (
            cfdi.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'),
            'http://www.sat.gob.mx/terceros',
            'http://www.sat.gob.mx/sitio_internet/cfd/terceros/terceros11.xsd')
        result['cfdi_node'] = cfdi
        return result


class AccountInvoiceLine(models.Model):
    _inherit = 'account.move.line'

    l10n_mx_edi_3rd_party_id = fields.Many2one(
        'res.partner', string='On Behalf of',
        help="If this product is being sold on behalf of a 3rd party, "
        "specifies who the sale is on behalf of.\n"
        "If set, the complement 3rd party will be used and the node "
        "will be filled according to the value set on this field.")
    # TODO: create logic to add more than one date per customs
    l10n_mx_edi_customs_date = fields.Date(
        string='Customs Expedition Date', copy=False,
        help="If this is an imported good, specifies the expedition date of "
        "the customs document that covers the importation of the good.")
    l10n_mx_edi_customs_name = fields.Char(
        string="Customs Office", copy=False,
        help="If this is an imported good, specifies the customs office by "
        "which the importation of the good was made.")
