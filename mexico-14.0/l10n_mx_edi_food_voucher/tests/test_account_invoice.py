from datetime import datetime
from lxml import objectify
from odoo import fields
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class TestL10nMxEdiInvoiceVoucher(TestMxEdiCommon):

    def test_l10n_mx_edi_voucher_invoice(self):
        self.certificate._check_credentials()
        product_model = self.env['product.product']
        partner_model = self.env['res.partner']
        detail = product_model.create({
            'name': 'Voucher Detail',
            'type': 'service',
            'categ_id': self.ref('product.product_category_all'),
            'unspsc_code_id': self.ref('product_unspsc.unspsc_code_01010101')
        })
        employee_lines = [
            partner_model.browse(self.ref('base.res_partner_address_4')),
            partner_model.browse(self.ref('base.res_partner_address_3'))]
        for employee in employee_lines:
            employee.parent_id.write({'country_id': self.ref('base.mx'), })
            employee.write({
                'vat': 'XAXX010101000',
                'ref': '4068010004070241',
                'l10n_mx_edi_curp': 'AAAA010101HCLJND07',
                'l10n_mx_edi_voucher_nss': '91234567890',
            })
        invoice = self.invoice
        invoice.partner_id = self.ref('base.res_partner_12')
        account = invoice.invoice_line_ids[0].account_id.id
        invoice.partner_bank_id = invoice.partner_bank_id.create({
            'partner_id': invoice.partner_id.id,
            'acc_number': '123456789',
        })
        invoice.line_ids.unlink()
        invoice.invoice_line_ids.unlink()
        invoice.invoice_line_ids = ([(0, 0, {
            'product_id': self.product.id,
            'name': self.product.name,
            'quantity': 1,
            'price_unit': 1500.00,
            'account_id': account,
            'product_uom_id': self.ref('uom.product_uom_unit'),
            'tax_ids': [self.tax_16.id]
        }), (0, 0, {
            'product_id': detail.id,
            'name': detail.name,
            'quantity': 0.0,
            'price_unit': 100.0,
            'account_id': account,
            'l10n_mx_edi_voucher_id': self.ref('base.res_partner_address_4'),
            'product_uom_id': self.ref('uom.product_uom_unit')
        }), (0, 0, {
            'product_id': detail.id,
            'name': detail.name,
            'quantity': 0.0,
            'price_unit': 100.0,
            'account_id': account,
            'l10n_mx_edi_voucher_id': self.ref('base.res_partner_address_3'),
            'product_uom_id': self.ref('uom.product_uom_unit')
        })])

        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml_str = generated_files[0]
        xml = objectify.fromstring(xml_str)
        cfdi_date = datetime.combine(
            fields.Datetime.from_string(invoice.invoice_date),
            invoice.l10n_mx_edi_post_time.time()).strftime('%Y-%m-%dT%H:%M:%S')
        xml_expected = objectify.fromstring(
            '<valesdedespensa:ValesDeDespensa '
            'xmlns:valesdedespensa="http://www.sat.gob.mx/valesdedespensa" '
            'version="1.0" tipoOperacion="monedero electrónico" numeroDeCuenta="123456789" total="200.0">'
            '<valesdedespensa:Conceptos>'
            '<valesdedespensa:Concepto identificador="4068010004070241" '
            'fecha="%(voucher_date)s" rfc="XAXX010101000" '
            'curp="AAAA010101HCLJND07" nombre="Floyd Steward" '
            'numSeguridadSocial="91234567890" importe="100.0"/>'
            '<valesdedespensa:Concepto identificador="4068010004070241" '
            'fecha="%(voucher_date)s" rfc="XAXX010101000" '
            'curp="AAAA010101HCLJND07" nombre="Douglas Fletcher" '
            'numSeguridadSocial="91234567890" importe="100.0"/>'
            '</valesdedespensa:Conceptos>'
            '</valesdedespensa:ValesDeDespensa>' % {
                'voucher_date': cfdi_date,
            })
        namespaces = {
            'valesdedespensa': 'http://www.sat.gob.mx/valesdedespensa'}
        comp = xml.Complemento.xpath('//valesdedespensa:ValesDeDespensa',
                                     namespaces=namespaces)
        self.assertEqualXML(comp[0], xml_expected)

    def xml2dict(self, xml):
        """Receive 1 lxml etree object and return a dict string.
        This method allow us have a precise diff output"""
        def recursive_dict(element):
            return (element.tag,
                    dict((recursive_dict(e) for e in element.getchildren()),
                         ____text=(element.text or '').strip(), **element.attrib))
        return dict([recursive_dict(xml)])

    def assertEqualXML(self, xml_real, xml_expected):  # pylint: disable=invalid-name
        """Receive 2 objectify objects and show a diff assert if exists."""
        xml_expected = self.xml2dict(xml_expected)
        xml_real = self.xml2dict(xml_real)
        # "self.maxDiff = None" is used to get a full diff from assertEqual method
        # This allow us get a precise and large log message of where is failing
        # expected xml vs real xml More info:
        # https://docs.python.org/2/library/unittest.html#unittest.TestCase.maxDiff
        self.maxDiff = None
        self.assertEqual(xml_real, xml_expected)
