import base64
import os

from lxml.objectify import fromstring

from odoo.tests.common import Form
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon
from odoo.tools import misc


class TestL10nMxEdiInvoiceFuel(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        self.partner_chinaexport = self.env.ref("base.res_partner_address_11")
        self.fuel_product = self.env.ref('l10n_mx_edi_fuel.res_product_fuel_diesel')
        self.fuel_product.sudo().write({
            'unspsc_code_id': self.ref('product_unspsc.unspsc_code_15101505'),
            'taxes_id': [(6, 0, [self.ref('l10n_mx.1_tax12')])],
        })
        self.service_station = self.env['res.partner'].create({
            'name': 'MX Service Station',
            'ref': '1234',
        })
        service_station_bank = self.env['res.partner.bank'].create({
            'bank_id': self.ref('base.res_bank_1'),
            'acc_number': '0987654321',
            'partner_id': self.service_station.id,
        })
        self.service_station.bank_ids = [service_station_bank.id]
        self.service_station.category_id = [self.ref('l10n_mx_edi_fuel.res_partner_category_service_station')]
        self.xml_expected_ecc = misc.file_open(os.path.join(
            'l10n_mx_edi_fuel', 'tests', 'expected_ecc.xml')).read().encode('UTF-8')
        self.xml_expected_cc = misc.file_open(os.path.join(
            'l10n_mx_edi_fuel', 'tests', 'expected_cc.xml')).read().encode('UTF-8')
        self.xml_expected_only_cc = misc.file_open(os.path.join(
            'l10n_mx_edi_fuel', 'tests', 'expected_only_cc.xml')).read().encode('UTF-8')
        self.xml_expected_ecc_discount = misc.file_open(os.path.join(
            'l10n_mx_edi_fuel', 'tests', 'expected_ecc_discount.xml')).read().encode('UTF-8')

    def create_fuel_invoice(self, service_station=None, inv_type='out_invoice', currency_id=None):
        if currency_id is None:
            currency_id = self.env['res.currency'].search([('name', '=', 'USD')]).id
        account_payment = self.env['res.partner.bank'].create({
            'acc_number': '123456789',
            'partner_id': self.partner_a.id})
        invoice = self.env['account.move'].create({
            'partner_id': self.partner_a.id,
            'move_type': inv_type,
            'currency_id': currency_id,
            'l10n_mx_edi_payment_method_id': self.env.ref('l10n_mx_edi.payment_method_efectivo').id,
            'partner_bank_id': account_payment.id,
            'l10n_mx_edi_usage': 'P01',
        })
        self.create_fuel_invoice_line(invoice, service_station)
        return invoice

    def create_fuel_invoice_line(self, invoice, service_station):
        move_form = Form(invoice)
        with move_form.invoice_line_ids.new() as line_form:
            line_form.price_unit = self.fuel_product.lst_price
            line_form.quantity = 1
            line_form.product_id = self.fuel_product
            if service_station:
                line_form.l10n_mx_edi_fuel_partner_id = service_station
        move_form.save()

    def test_l10n_mx_edi_ecc_invoice(self):
        self.invoice.company_id.write({'l10n_mx_edi_isepi': True, })
        self.partner_chinaexport.parent_id.write(
            {'ref': '0000123',
             'vat': 'XEXX010101000',
             'country_id': self.env.ref('base.mx').id, })
        self.partner_a.commercial_partner_id.write(
            {'vat': 'EKU9003173C9',
             'country_id': self.env.ref('base.mx').id})

        invoice = self.create_fuel_invoice(self.service_station)
        invoice.partner_id = self.partner_chinaexport.parent_id
        invoice.action_post()
        generated_files = self.env['account.edi.document'].sudo().with_context(edi_test_mode=False).search(
            [('state', 'in', ('to_send', 'to_cancel'))])._process_documents_web_services()
        self.assertEqual(invoice.edi_state, "sent", invoice.edi_document_ids.mapped('error'))
        xml = fromstring((base64.decodebytes(
            invoice._get_l10n_mx_edi_signed_edi_document().attachment_id.with_context(bin_size=False).datas)))
        namespaces = {'ecc12': 'http://www.sat.gob.mx/EstadoDeCuentaCombustible12'}
        ecc12 = xml.Complemento.xpath('//ecc12:EstadoDeCuentaCombustible', namespaces=namespaces)
        self.assertTrue(ecc12, 'Complement to ECC12 not added correctly')
        xml_expected = fromstring(self.xml_expected_ecc)
        self.xml_merge_dynamic_items(xml, xml_expected)
        xml_expected.attrib['Folio'] = xml.attrib['Folio']
        xml_expected.attrib['TipoCambio'] = xml.attrib['TipoCambio']
        self.assertEqualXML(xml, xml_expected)

        # Generating a refund to test consumodecombustible complement
        # when company is only an emitter
        refund = self.env['account.move.reversal'].with_context(
            active_model='account.move', active_ids=invoice.ids).create({'refund_method': 'refund', })
        result = refund.reverse_moves()
        refund = self.env['account.move'].browse(result['res_id'])
        self.assertFalse(refund.invoice_line_ids.filtered('l10n_mx_edi_fuel_partner_id'), 'Service Station not clean')
        refund.invoice_date = invoice.invoice_date
        refund.name = '0000123'
        refund.partner_bank_id.unlink()
        refund.partner_id = self.service_station
        refund.partner_bank_id = self.service_station.bank_ids.id
        refund.l10n_mx_edi_payment_method_id = invoice.l10n_mx_edi_payment_method_id.id
        refund.l10n_mx_edi_usage = 'P01'
        refund.action_post()
        generated_files = self._process_documents_web_services(refund, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        self.assertEqual(refund.edi_state, "sent", refund.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        namespaces = {'consumodecombustibles11': 'http://www.sat.gob.mx/ConsumoDeCombustibles11'}
        cc = xml.Complemento.xpath('//consumodecombustibles11:ConsumoDeCombustibles', namespaces=namespaces)
        self.assertTrue(cc, 'Complement to ConsumoDeCombustibles not added correctly')
        xml_expected = fromstring(self.xml_expected_cc)
        self.xml_merge_dynamic_items(xml, xml_expected)
        xml_expected.attrib['Folio'] = xml.attrib['Folio']
        xml.attrib['Serie'] = xml_expected.attrib['Serie']
        xml_expected.attrib['TipoCambio'] = xml.attrib['TipoCambio']
        xml_expected.CfdiRelacionados.CfdiRelacionado.attrib['UUID'] = xml.CfdiRelacionados.CfdiRelacionado.attrib['UUID'] # noqa
        self.assertEqualXML(xml, xml_expected)

        # Testing with discount
        invoice = self.create_fuel_invoice(self.service_station)
        move_form = Form(invoice)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.discount = 13.0
        move_form.save()
        invoice.partner_id = self.partner_chinaexport.parent_id
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        xml_expected = fromstring(self.xml_expected_ecc_discount)
        self.xml_merge_dynamic_items(xml, xml_expected)
        xml_expected.attrib['Folio'] = xml.attrib['Folio']
        xml_expected.attrib['TipoCambio'] = xml.attrib['TipoCambio']
        self.assertEqualXML(xml, xml_expected)

    def test_l10n_mx_edi_cc_invoice(self):
        company = self.invoice.company_id
        company.write({'l10n_mx_edi_isepi': False, })
        company.partner_id.ref = '1234'
        company.partner_id.category_id = [self.ref('l10n_mx_edi_fuel.res_partner_category_service_station')]
        self.partner_a.parent_id.write(
            {'vat': 'EKU9003173C9',
             'country_id': self.env.ref('base.mx').id})
        invoice = self.create_fuel_invoice()
        invoice.l10n_mx_edi_emitter_reference = "123456|000008955"
        invoice.l10n_mx_edi_origin = "01|B4536414-607E-42CA-AAB4-03EB964002A1"
        invoice.partner_id = self.partner_a.commercial_partner_id
        # invoice.move_name = 'INV/2018/1000'
        invoice.action_post()
        generated_files = self._process_documents_web_services(invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        namespaces = {'consumodecombustibles11': 'http://www.sat.gob.mx/ConsumoDeCombustibles11'}
        cc = xml.Complemento.xpath('//consumodecombustibles11:ConsumoDeCombustibles', namespaces=namespaces)
        self.assertTrue(cc, 'Complement to ConsumoDeCombustibles not added ' 'correctly')
        xml_expected = fromstring(self.xml_expected_only_cc)
        self.xml_merge_dynamic_items(xml, xml_expected)
        xml_expected.attrib['Folio'] = xml.attrib['Folio']
        xml_expected.attrib['TipoCambio'] = xml.attrib['TipoCambio']
        xml_expected.CfdiRelacionados.CfdiRelacionado.attrib['UUID'] = xml.CfdiRelacionados.CfdiRelacionado.attrib['UUID'] # noqa
        self.assertEqualXML(xml, xml_expected)

    def xml_merge_dynamic_items(self, xml, xml_expected):
        xml_expected.attrib['Fecha'] = xml.attrib['Fecha']
        xml_expected.attrib['Sello'] = xml.attrib['Sello']
        if xml.get('Serie'):
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
