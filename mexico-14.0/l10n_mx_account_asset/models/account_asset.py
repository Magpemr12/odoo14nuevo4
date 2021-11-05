# Copyright 2019 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _prepare_sale_move(self, move_vals):
        """This method creates an account move that has the following lines:
           - Asset with the cogs account, whose amount is the residual value of the asset.
           - Asset with the accumulated depreciation account, whose amount is
           the difference between gross value and the residual of the asset.
           - Asset with the asset account, whose amount is the gross value.

           :param move_vals: A values list initialized by method _prepare_move_for_asset_depreciation
           :type move_vals: list of dictionaries
           :return: A list of diccionaries, values to create an asset sale account move
           :rtype: list of dictionaries
        """
        asset_id = self.env['account.asset'].browse(move_vals['asset_id'])
        account_analytic_id = asset_id.account_analytic_id
        analytic_tag_ids = asset_id.analytic_tag_ids
        depreciation_date = (move_vals['date'] or asset_id.get_mx_current_datetime())
        company_currency = asset_id.company_id.currency_id
        current_currency = asset_id.currency_id
        prec = company_currency.decimal_places
        asset_name = asset_id.name
        amount = current_currency._convert(
            move_vals['amount_total'], company_currency, asset_id.company_id,
            depreciation_date)
        value = current_currency._convert(
            asset_id.original_value, company_currency, asset_id.company_id,
            depreciation_date)

        # /!\ NOTE: Reverse Asset Account
        move_line_1 = {
            'name': asset_name,
            'account_id': asset_id.account_asset_id.id,
            'debit':
                0.0 if float_compare(value, 0.0, precision_digits=prec) > 0
                else -value,
            'credit':
                value if float_compare(value, 0.0, precision_digits=prec) > 0
                else 0.0,
            'analytic_account_id': asset_id.asset_type == 'sale' and account_analytic_id.id,
            'analytic_tag_ids': asset_id.asset_type == 'sale' and [(6, 0, analytic_tag_ids.ids)],
            'currency_id': company_currency != current_currency and current_currency.id,
            'amount_currency': -asset_id.orignal_value if company_currency != current_currency else 0.0,
        }
        # /!\ NOTE: Reverse Cumulative Account
        move_line_2 = {
            'name': asset_name,
            'account_id': asset_id.account_depreciation_id.id,
            'debit':
                (value - amount) if float_compare(
                    value - amount, 0.0, precision_digits=prec) > 0
                else 0.0,
            'credit':
                0.0 if float_compare(
                    value - amount, 0.0, precision_digits=prec) > 0
                else -(value - amount),
            'analytic_account_id': asset_id.asset_type == 'sale' and account_analytic_id.id,
            'analytic_tag_ids': asset_id.asset_type == 'sale' and [(6, 0, analytic_tag_ids.ids)],
            'currency_id': company_currency != current_currency and current_currency.id,
            'amount_currency':
                (asset_id.original_value - move_vals['amount_total'])
                if company_currency != current_currency
                else 0.0,
        }
        # /!\ NOTE: Cogs Account
        move_line_3 = {
            'name': asset_name,
            'account_id': asset_id.account_cogs_id.id,
            'debit':
                amount if float_compare(amount, 0.0, precision_digits=prec) > 0
                else 0.0,
            'credit':
                0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0
                else -amount,
            'analytic_account_id': asset_id.asset_type == 'purchase' and account_analytic_id.id,
            'analytic_tag_ids': asset_id.asset_type == 'purchase' and [(6, 0, analytic_tag_ids.ids)],
            'currency_id': company_currency != current_currency and current_currency.id,
            'amount_currency': move_vals['amount_total'] if company_currency != current_currency else 0.0,
        }
        move_vals.update({
            'date': depreciation_date or False,
            'to_check': True,
            'auto_post': False,
            'line_ids': [
                (0, 0, move_line_1), (0, 0, move_line_2), (0, 0, move_line_3)],
        })
        return move_vals

    @api.model
    def create_sale_move(self, vals, post_move=True):
        asset_id = self.env['account.asset'].browse(vals['asset_id'])
        if not asset_id.account_cogs_id:
            raise UserError(_(
                'COGS account of asset category needs to be configured. '
                'Please check the asset category.'))
        move_vals = self._prepare_sale_move(vals)
        move_id = self.env['account.move'].create(move_vals)

        if post_move and move_id and move_id.asset_id.state == "open":
            move_id.post()
        return move_id


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    account_cogs_id = fields.Many2one(
        'account.account', string='COGS Account',
        domain=[('internal_type', '=', 'other'), ('deprecated', '=', False)],
        help="Account used to record sale of the asset."
    )

    def get_mx_current_datetime(self):
        return fields.Datetime.context_timestamp(
            self.with_context(tz='America/Mexico_City'), fields.Datetime.now())

    def _get_sale_moves(self):
        move_ids = []
        for asset in self:
            unposted_depreciation_move_ids = asset.depreciation_move_ids.filtered(lambda x: x.state == 'draft')
            if not unposted_depreciation_move_ids:
                continue

            # Remove all unposted depr. lines
            commands = [
                (2, line_id.id, False)
                for line_id in unposted_depreciation_move_ids]

            # Create a new depr. line with the residual amount and post it
            sequence = len(asset.depreciation_move_ids) - len(unposted_depreciation_move_ids) + 1
            today = self.get_mx_current_datetime()
            vals = {
                'amount': asset.value_residual,
                'asset_id': asset,
                'sequence': sequence,
                'move_ref': (asset.name or '') + '/' + str(sequence),
                'asset_remaining_value': 0,
                # the asset is completely depreciated
                'asset_depreciated_value': asset.original_value - asset.salvage_value,
                'date': today,
            }
            vals = self.env['account.move']._prepare_move_for_asset_depreciation(vals)
            move_id = self.env['account.move'].create_sale_move(vals, post_move=False)
            commands.append((4, move_id.id, 0))
            asset.write({
                'depreciation_move_ids': commands,
                'method_number': sequence
            })
            tracked_fields = self.env['account.asset'].fields_get(
                ['method_number', 'method_end'])
            changes, tracking_value_ids = asset._message_track(
                tracked_fields, {'method_number': asset.method_number})
            if changes:
                asset.message_post(
                    body=_('Asset sold. '
                           'Accounting entry awaiting for validation.'),
                    tracking_value_ids=tracking_value_ids)
            move_ids += move_id.ids
            asset.state = 'close'
        return move_ids

    def sale_and_set_to_close(self):
        move_ids = self._get_sale_moves()
        if move_ids:
            name = _('Sale Move')
            view_mode = 'form'
            if len(move_ids) > 1:
                name = _('Sale Moves')
                view_mode = 'tree,form'
            return {
                'name': name,
                'view_mode': view_mode,
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': move_ids[0],
            }
        # Fallback, as if we just clicked on the smartbutton
        return self.open_entries()

    def reopen_asset(self):
        self.write({'state': 'open'})
        self.message_post(body=_('This fixed asset has been reopened.'))
