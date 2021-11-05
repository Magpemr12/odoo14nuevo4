# Copyright 2019 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


class TestAttachmentZip(TestMxEdiCommon):

    def test_attachment_zip(self):
        invoice = self.invoice
        invoice.action_post()
        self._process_documents_web_services(invoice, {'cfdi_3_3'})
        attach_zip = self.env['ir.attachment.zip'].create({
            'attachment_ids': [(6, 0, invoice.edi_document_ids.mapped('attachment_id').ids)],
            'zip_name': 'test01.zip',
        })
        attach_zip._set_zip_file()
        # action = attach_zip._get_action_download()
        # TODO: add asserts reading zip content
