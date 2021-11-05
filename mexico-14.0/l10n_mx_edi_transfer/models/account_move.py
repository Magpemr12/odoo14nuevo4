import base64
from lxml.objectify import fromstring
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _stock_account_prepare_anglo_saxon_out_lines_vals(self):
        """If it is a 'traslado' invoice then skip inventory account moves"""
        records = self.filtered(lambda i: i.l10n_mx_edi_cfdi_request in ('on_invoice', 'on_refund') and
                                i.company_id.partner_id.commercial_partner_id == i.partner_id.commercial_partner_id)
        return super(AccountMove, self - records)._stock_account_prepare_anglo_saxon_out_lines_vals()

    def _l10n_mx_edi_decode_cfdi(self, cfdi_data=None):
        """If the CFDI was signed, try to adds the schemaLocation correctly"""
        result = super()._l10n_mx_edi_decode_cfdi(cfdi_data=cfdi_data)
        # Find a signed cfdi.
        if not cfdi_data:
            signed_edi = self._get_l10n_mx_edi_signed_edi_document()
            if signed_edi:
                cfdi_data = base64.decodebytes(signed_edi.attachment_id.with_context(bin_size=False).datas)

        # Nothing to decode.
        if not cfdi_data:
            return {}

        cfdi_node = fromstring(cfdi_data)
        result['document_type'] = cfdi_node.get('TipoDeComprobante')
        return result
