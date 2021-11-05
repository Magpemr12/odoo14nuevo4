import os

from lxml.objectify import fromstring

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.tools import misc


class TestL10nMxEdiInvoiceImpLocal(TestMxEdiCommon):

    def test_l10n_mx_edi_implocal(self):
        self.certificate._check_credentials()
        self.tag_model = self.env['account.account.tag']
        self.tax_local = self.tax_16.copy({
            'name': 'LOCAL(10%) VENTAS',
            'amount': 10.000000,
        })
        for rep_line in self.tax_16.invoice_repartition_line_ids:
            rep_line.tag_ids |= self.env.ref('l10n_mx.tag_iva')
        for rep_line in self.tax_10_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= self.env.ref('l10n_mx.tag_isr')
        for rep_line in self.tax_local.invoice_repartition_line_ids:
            rep_line.tag_ids |= self.env.ref(
                'l10n_mx_edi_implocal.account_tax_local')
        self.product = self.env.ref("product.product_product_2")
        self.product.taxes_id = [self.tax_16.id, self.tax_10_negative.id,
                                 self.tax_local.id]
        self.product.default_code = "TEST"
        self.product.unspsc_code_id = self.ref('product_unspsc.unspsc_code_01010101')
        self.xml_expected = misc.file_open(os.path.join(
            'l10n_mx_edi_implocal', 'tests', 'expected.xml')).read().encode('UTF-8')

        invoice = self.invoice
        invoice.company_id.sudo().name = 'YourCompany MX'
        invoice.currency_id = self.env.ref('base.MXN')
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': self.product.id,
            'quantity': 1,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line_dict = invoice_line._convert_to_write(invoice_line._cache)
        invoice_line_dict['price_unit'] = 450
        invoice.invoice_line_ids = [(0, 0, invoice_line_dict)]
        invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        namespaces = {'implocal': 'http://www.sat.gob.mx/implocal'}
        comp = xml.Complemento.xpath('//implocal:ImpuestosLocales',
                                     namespaces=namespaces)
        self.assertTrue(comp, 'Complement to implocal not added correctly')
        xml_expected = fromstring(self.xml_expected)
        self.xml_merge_dynamic_items(xml, xml_expected)
        self.assertEqualXML(xml, xml_expected)

    def xml_merge_dynamic_items(self, xml, xml_expected):
        xml_expected.attrib['Folio'] = xml.attrib['Folio']
        xml_expected.attrib['Fecha'] = xml.attrib['Fecha']
        xml_expected.attrib['Sello'] = xml.attrib['Sello']
        xml_expected.attrib['Serie'] = xml.attrib['Serie']
        xml_expected.Complemento = xml.Complemento

    def xml2dict(self, xml):
        """Receive 1 lxml etree object and return a dict string.
        This method allow us have a precise diff output"""
        def recursive_dict(element):
            return (element.tag,
                    dict((recursive_dict(e) for e in element.getchildren()),
                         ____text=(element.text or '').strip(), **element.attrib))
        return dict([recursive_dict(xml)])

    def assertEqualXML(self, xml_real, xml_expected):
        """Receive 2 objectify objects and show a diff assert if exists."""
        xml_expected = self.xml2dict(xml_expected)
        xml_real = self.xml2dict(xml_real)
        # "self.maxDiff = None" is used to get a full diff from assertEqual method
        # This allow us get a precise and large log message of where is failing
        # expected xml vs real xml More info:
        # https://docs.python.org/2/library/unittest.html#unittest.TestCase.maxDiff
        self.maxDiff = None
        self.assertEqual(xml_real, xml_expected)
