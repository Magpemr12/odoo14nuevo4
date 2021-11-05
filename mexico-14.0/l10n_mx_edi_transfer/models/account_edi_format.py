from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        values = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        if invoice.company_id.partner_id.commercial_partner_id != invoice.partner_id.commercial_partner_id:  # noqa
            return values
        invoice_lines = values['invoice_line_values']
        values.update({
            'document_type': 'T',
            'payment_policy': None,
            'discount_amount': None,
            'total_amount_untaxed_wo_discount': sum(vals['total_wo_discount'] for vals in invoice_lines),
            'total_amount_untaxed_discount': sum(vals['discount_amount'] for vals in invoice_lines),
            'total_discount': lambda l, d: False,
            # NumRegIdTrib equal to None if Emisor == Receptor (CFDI type == T)
            'receiver_reg_trib': None,
        })
        return values
