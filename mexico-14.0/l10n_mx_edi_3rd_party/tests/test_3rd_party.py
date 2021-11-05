# Copyright 2018 Vauxoo
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl).

import os

from lxml.objectify import fromstring

from odoo import tools
from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class Test3rdParty(TestMxEdiCommon):

    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        iva_tag = self.env['account.account.tag'].search(
            [('name', '=', 'IVA')])
        for rep_line in self.tax_16.invoice_repartition_line_ids:
            rep_line.tag_ids |= iva_tag
        isr_tag = self.env['account.account.tag'].search(
            [('name', '=', 'ISR')])
        for rep_line in self.tax_10_negative.invoice_repartition_line_ids:
            rep_line.tag_ids |= isr_tag
        self.namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/3',
            'terceros': 'http://www.sat.gob.mx/terceros',
        }
        self.third = self.env.ref('base.res_partner_main2')
        self.third.write({
            'city_id': self.ref('l10n_mx_edi.res_city_mx_son_001'),
            'street_name': 'Campobasso Norte',
            'street_number': 3206,
        })

    def create_invoice_line_to_3rd(self, invoice, product):
        invoice_line = invoice.invoice_line_ids.new({
            'product_id': product.id,
            'quantity': 1,
            'l10n_mx_edi_3rd_party_id': self.third.id,
            'move_id': invoice.id,
        })
        invoice_line._onchange_product_id()
        invoice_line.move_id = False
        line = invoice_line._convert_to_write({
            name: invoice_line[name] for name in invoice_line._cache
        })
        line['tax_ids'] = [(4, self.tax_16.id), (4, self.tax_10_negative.id)]
        return line

    def test_xml_node(self):
        """Validates the XML node of the third party complement

        Validates that the XML node ``<terceros:PorCuentadeTerceros>`` is
        included, and that its content is generated correctly.

        This test covers all three possible cases of products sold on
        behalf of third parties:
        1. The product is imported and sold first hand
        2. The product is made from other products (parts or components). This
           also covers the case when one of its parts is imported and sold
           first hand.
        3. The product is a lease
        """
        invoice = self.invoice

        # Case 1: the product is imported and sold first hand
        imported_product = self.env.ref('product.product_product_24')
        imported_product.write({
            'unspsc_code_id': self.ref('product_unspsc.unspsc_code_43201401'),
        })
        line = self.create_invoice_line_to_3rd(invoice, imported_product)
        line['l10n_mx_edi_customs_number'] = '15  48  3009  0001234'
        line['l10n_mx_edi_customs_date'] = '2015-01-01'
        line['l10n_mx_edi_customs_name'] = "Mexico City's customs"
        line['tax_ids'] = False
        invoice.invoice_line_ids = [(0, 0, line)]

        # Case 2: the product is made from other products
        # There's a BoM for the default product, it doesn't need to be created
        line = self.create_invoice_line_to_3rd(invoice, self.product)
        invoice.invoice_line_ids = [(0, 0, line)]
        bom = self.env.ref('mrp.mrp_bom_manufacture')
        bom.sudo().write({'company_id': invoice.company_id.id})
        self.product.bom_ids = [(4, bom.ids)]
        self.product.bom_ids.sudo().bom_line_ids[0].write({
            'l10n_mx_edi_customs_number': '15  48  3009  0001234',
            'l10n_mx_edi_customs_date': '2015-01-01',
            'l10n_mx_edi_customs_name': "Mexico City's customs",
        })

        # Case 3: the product is a lease
        lease_product = self.env.ref('product.product_product_1')
        lease_product.write({
            'name': 'House Lease',
            'unspsc_code_id': self.ref('product_unspsc.unspsc_code_80131501'),
            'l10n_mx_edi_property_tax': 'CP1234',
        })
        line = self.create_invoice_line_to_3rd(invoice, lease_product)
        line['tax_ids'] = False
        invoice.invoice_line_ids = [(0, 0, line)]
        invoice.action_post()
        generated_files = self._process_documents_web_services(self.invoice, {'cfdi_3_3'})
        self.assertTrue(generated_files)
        self.assertEqual(invoice.edi_state, "sent", invoice.message_ids.mapped('body'))
        xml = fromstring(generated_files[0])
        self.assertEqual(
            len(xml.Conceptos.Concepto), 4,
            "There should be exactly four nodes 'Concepto'")
        # Retrieve nodes <PorCuentadeTerceros> from all concepts
        node0 = xml.Conceptos.Concepto[0].find(
            'cfdi:ComplementoConcepto/terceros:PorCuentadeTerceros',
            namespaces=self.namespaces)
        node1 = xml.Conceptos.Concepto[1].find(
            'cfdi:ComplementoConcepto/terceros:PorCuentadeTerceros',
            namespaces=self.namespaces)
        node2 = xml.Conceptos.Concepto[2].find(
            'cfdi:ComplementoConcepto/terceros:PorCuentadeTerceros',
            namespaces=self.namespaces)
        node3 = xml.Conceptos.Concepto[3].find(
            'cfdi:ComplementoConcepto/terceros:PorCuentadeTerceros',
            namespaces=self.namespaces)
        # All but the first node shoulb be present
        error_msg = ("Node <terceros:PorCuentadeTerceros> should%sbe present for concept #%s")
        self.assertIsNone(node0, error_msg % (' not ', '1'))
        self.assertIsNotNone(node1, error_msg % (' ', '2'))
        self.assertIsNotNone(node2, error_msg % (' ', '3'))
        self.assertIsNotNone(node2, error_msg % (' ', '3'))

        xmlpath = os.path.join(os.path.dirname(__file__), 'expected_nodes.xml')
        with tools.file_open(xmlpath, mode='rb') as xmlfile:
            xml_expected = fromstring(xmlfile.read())
        nodes_expected = xml_expected.findall(
            'terceros:PorCuentadeTerceros', namespaces=self.namespaces)
        self.assertEqualXML(node1, nodes_expected[0])
        self.assertEqualXML(node2, nodes_expected[1])
        self.assertEqualXML(node3, nodes_expected[2])

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
