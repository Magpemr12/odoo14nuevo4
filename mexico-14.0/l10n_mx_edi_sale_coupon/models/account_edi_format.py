from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        cfdi_values = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        # Avoid affect the transfer module
        invoice_lines = invoice.invoice_line_ids.filtered(lambda inv: not inv.display_type)
        if invoice.company_id.partner_id.commercial_partner_id != invoice.partner_id.commercial_partner_id:
            invoice_lines = invoice_lines.filtered(lambda inv: inv.price_unit)
        cfdi_values['invoice_line_values'] = []
        for line in invoice_lines:
            cfdi_values['invoice_line_values'].append(self._l10n_mx_edi_get_invoice_line_cfdi_values(invoice, line))
        return cfdi_values
