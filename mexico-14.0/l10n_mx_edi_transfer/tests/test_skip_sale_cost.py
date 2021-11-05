from lxml.objectify import fromstring
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.tests.common import Form


class TestMxEdiTrasladoInvoice(TestMxEdiCommon):

    def test_traslado_invoice(self):
        self.certificate._check_credentials()
        company = self.invoice.company_id
        self.invoice.partner_id = company.partner_id
        self.invoice.currency_id = self.invoice.company_currency_id
        move_form = Form(self.invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.price_unit = 0.0
            line_form.quantity = 1
            line_form.tax_ids.clear()
        move_form.save()
        self.invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        xml = fromstring(generated_files[0])
        self.assertEqual(xml.get('TipoDeComprobante'), 'T')
        self.assertEqual(xml.get('Total'), '0.00')
        self.assertEqual(xml.Conceptos.Concepto[0].get('Descripcion'), 'TRASLADO DE MERCANCIAS product_mx')
