# Copyright 2019 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class TestL10nMxAccountAsset(TestMxEdiCommon):
    def setUp(self):
        super(TestL10nMxAccountAsset, self).setUp()
        self.account_asset_id = self.create_account(
            'Computer equipment - (test)', '15601001', self.env.ref('account.data_account_type_fixed_assets').id)
        self.account_depreciation_id = self.create_account(
            'Accum. Dep. of fixed assets - (test)', '17102001',
            self.env.ref('account.data_account_type_fixed_assets').id)
        self.account_depreciation_expense_id = self.create_account(
            'Depreciation of Computer equipment - (test)', '61305103',
            self.env.ref('account.data_account_type_depreciation').id)
        self.account_cogs_id = self.create_account(
            'Cost of sales of fixed assets - (test)', '501.01.005',
            self.env.ref('account.data_account_type_direct_costs').id)

        self.journal_id = self.env['account.journal'].create({
            'name': 'Depreciation and Amortization - Test',
            'type': 'general',
            'code': 'DPAM',
        })
        # This record is already created in demo data
        self.asset = self.env.ref('l10n_mx_account_asset.account_asset_test_mx').create({
            'name': 'Computer X109',
            'state': 'draft',
            'company_id': self.env.user.company_id.id,
            'first_depreciation_date': date.today(),
            'acquisition_date': date.today(),
            'account_asset_id': self.account_asset_id.id,
            'account_depreciation_id': self.account_depreciation_id.id,
            'account_depreciation_expense_id': self.account_depreciation_expense_id.id,
            'account_cogs_id': self.account_cogs_id.id,
            'journal_id': self.journal_id.id,
            'original_value': 60000.00,
            'asset_type': 'purchase',
            'method_number': 12,
            # Method period months
            'method_period': '1',
        })

    def test_00_account_asset_asset(self):
        asset = self.asset
        # Compute depreciation lines for asset
        asset.compute_depreciation_board()
        asset.validate()
        self.assertEqual(asset.method_number, len(asset.depreciation_move_ids),
                         'Depreciation lines not created correctly')
        # The first move should be already posted by compute_depreciation_board
        first_move = asset.depreciation_move_ids.filtered(lambda m: m.date == date.today() and m.state == 'posted')
        self.assertTrue(first_move, 'The first move is not correctly initializated by compute_depreciation_board')

        # Save values, using them afther
        value_residual = asset.value_residual
        gross_value = asset.original_value
        accum_depreciation = gross_value - value_residual
        # The sale_and_set_to_close method returns a view of the moves.
        # The method that really makes the moves is _get_sale_moves
        sale_move = self.env['account.move'].browse(asset._get_sale_moves())
        sale_move.action_post()

        # There is a line in the move that contains the asset's cogs account
        # with the residual amount of the asset.
        cogs_line = sale_move.mapped('line_ids').filtered(
            lambda a: a.account_id == asset.account_cogs_id)
        self.assertTrue(cogs_line)
        self.assertEqual(
            cogs_line.debit or cogs_line.credit, value_residual)

        # There is a line in the move that contains the asset's Asset Account
        # with the gross value of the asset
        asset_line = sale_move.mapped('line_ids').filtered(
            lambda a: a.account_id == asset.account_asset_id)
        self.assertTrue(asset_line)
        self.assertEqual(asset_line.credit or asset_line.debit, gross_value)

        # There is a line in the move that contains the asset's
        # Depreciation Account with the difference between gross value and
        # the residual of the asset
        depreciation_line = sale_move.mapped('line_ids').filtered(
            lambda a: a.account_id == asset.account_depreciation_id)  # noqa
        self.assertTrue(depreciation_line)
        self.assertEqual(
            depreciation_line.debit or depreciation_line.credit, accum_depreciation)  # noqa
        # The asset is close after sell it
        self.assertEqual(asset.state, 'close')
        # Reopen asset
        asset.reopen_asset()
        self.assertEqual(asset.state, 'open')

    def test_01_account_asset_asset(self):
        asset = self.asset
        # Compute depreciation lines for asset
        asset.compute_depreciation_board()
        asset.validate()
        result = asset.sale_and_set_to_close()
        self.assertTrue(isinstance(result, dict), 'The asset sale has failed')

    def create_account(self, code, name, user_type_id=False):
        return self.env['account.account'].create({
            'name': name,
            'code': code,
            'user_type_id': user_type_id,
        })
