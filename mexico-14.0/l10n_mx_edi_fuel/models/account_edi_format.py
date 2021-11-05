from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _l10n_mx_edi_get_invoice_cfdi_values(self, invoice):
        values = super()._l10n_mx_edi_get_invoice_cfdi_values(invoice)
        fuel_billing = invoice.invoice_line_ids.filtered('product_id.l10n_mx_edi_fuel_billing')
        if not fuel_billing:
            return values
        values['fuel_lines'] = fuel_billing
        values['fuel_amount_untaxed'] = sum(fuel_billing.mapped(lambda l: l.quantity * l.price_unit))
        fuel_total_tax = invoice._get_fuel_taxes(fuel_billing)
        values['fuel_amount_total'] = values['fuel_amount_untaxed'] + fuel_total_tax
        return values
