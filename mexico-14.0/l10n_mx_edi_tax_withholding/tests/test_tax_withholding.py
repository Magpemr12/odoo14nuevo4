import base64
from os.path import join
from lxml.objectify import fromstring

from odoo.tools import misc
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class TestTaxWithholding(TestMxEdiCommon):

    def test_tax_withholding(self):
        """Ensure that XML is generated correctly"""
        payment = self.prepare_payment(11929208.33)
        payment._onchange_tax_withholding()
        payment.action_post()
        self.env['account.edi.document'].sudo().with_context(edi_test_mode=False).search(
            [('state', 'in', ('to_send', 'to_cancel'))])._process_documents_web_services()
        self.assertEqual(payment.move_id.edi_state, "sent", payment.move_id.message_ids.mapped('body'))
        xml = fromstring((base64.decodebytes(
            payment.move_id._get_l10n_mx_edi_signed_edi_document().attachment_id.with_context(bin_size=False).datas)))
        xml_expected = fromstring(misc.file_open(join(
            'l10n_mx_edi_tax_withholding', 'tests', 'expected.xml')).read().encode('UTF-8'))
        xml_expected.attrib['FechaExp'] = xml.attrib['FechaExp']
        xml_expected.attrib['Sello'] = xml.attrib['Sello']
        xml_expected.Complemento = xml.Complemento
        self.assertEqualXML(xml, xml_expected)

    def test_tax_withholding_usd(self):
        """Ensure that XML is generated correctly in usd"""
        payment = self.prepare_payment(497172.85)
        payment.currency_id = self.env.ref('base.USD')
        payment.l10n_mx_edi_tax_withholding_rate = 19.8145
        payment._onchange_tax_withholding()
        payment.action_post()
        self.env['account.edi.document'].sudo().with_context(edi_test_mode=False).search(
            [('state', 'in', ('to_send', 'to_cancel'))])._process_documents_web_services()
        self.assertEqual(payment.move_id.edi_state, "sent", payment.edi_document_ids.mapped('error'))
        xml = fromstring((base64.decodebytes(
            payment.move_id._get_l10n_mx_edi_signed_edi_document().attachment_id.with_context(bin_size=False).datas)))
        xml_expected = fromstring(misc.file_open(join(
            'l10n_mx_edi_tax_withholding', 'tests', 'expected_usd.xml')).read().encode('UTF-8'))
        xml_expected.attrib['FechaExp'] = xml.attrib['FechaExp']
        xml_expected.attrib['Sello'] = xml.attrib['Sello']
        xml_expected.Complemento = xml.Complemento
        self.assertEqualXML(xml, xml_expected)

    def prepare_payment(self, amount):
        self.certificate._check_credentials()
        self.partner_a.country_id = self.env.ref('base.us')
        self.partner_a.name = 'Google LLC'
        self.env.user.tz = 'America/Mexico_City'
        tax = self.env.ref('l10n_mx_edi_tax_withholding.tax_withholding')
        tax.sudo().company_id = self.invoice.company_id
        return self.payment.create({
            'date': '2021-04-15',
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_a.id,
            'payment_method_id': self.env.ref('account.account_payment_method_manual_out').id,
            'journal_id': self.company_data['default_journal_bank'].id,
            'amount': amount,
            'l10n_mx_edi_is_tax_withholding': True,
            'l10n_mx_edi_tax_withholding_id': tax.id,
            'l10n_mx_edi_tax_withholding_amount': 1.00,
            'l10n_mx_edi_tax_withholding_type': 'definitivo',
            'l10n_mx_edi_tax_withholding_concept': 'Pago de regalias',
        })

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
