from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class TestReport(TestMxEdiCommon):

    def test_01_render_report(self):
        invoice = self.invoice.copy()
        report = self.env['ir.actions.report']._get_report_from_name(
            'l10n_mx_edi_account_move_report.account_entries_report')
        self.assertEqual(len(report._render(invoice.id)), 2)

        payment = self.payment.copy()
        self.assertEqual(len(report._render(payment.move_id.id)), 2)
