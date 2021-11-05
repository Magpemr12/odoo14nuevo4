from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_mx_edi_emitter_reference = fields.Char(
        string="Electronic Purse Issuer Reference",
        help="This is needed when a service station invoice a fuel consumption given an electronic purse issuer "
        "credit note. The format should be: 'electronic purse number|electronic purse identifier owner bank account'."
        "ex.: 1234|0001234")

    def _reverse_move_vals(self, default_values, cancel=True):
        vals = super()._reverse_move_vals(default_values=default_values, cancel=cancel)
        if self.move_type not in ['out_refund', 'out_invoice', 'in_refund', 'in_invoice']:
            return vals
        for line in vals.get('line_ids', []):
            line[2].update({'l10n_mx_edi_fuel_partner_id': False})
        return vals

    def _get_fuel_taxes(self, lines):
        result = False
        if not lines:
            return result
        for line in lines:
            for tax in line.tax_ids.filtered(lambda r: r.amount > 0 and r.l10n_mx_tax_type != 'Exento'):
                result += round(abs(tax.amount / 100.0 * line.price_subtotal), 2)
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_mx_edi_fuel_partner_id = fields.Many2one(
        'res.partner', string='Service Station',
        help='Service Station information, set this if the company is an electronic purse issuer and you are issuing '
        'an Invoice')
