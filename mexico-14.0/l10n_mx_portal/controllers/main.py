# Copyright 2019 Vauxoo (https://www.vauxoo.com) <info@vauxoo.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _
from odoo.http import Controller, request, route
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.account.controllers.portal import PortalAccount as PA
from odoo import http


class SendInvoiceAndXML(Controller):

    @route(
        ['/send_invoice_mail/<int:invoice_id>', ],
        type='http', auth='user', website=True)
    def send_invoice_and_xml(self, invoice_id=None, **data):
        invoice_obj = request.env['account.move']
        invoice = invoice_obj.browse(invoice_id)
        template = request.env.ref('account.email_template_edi_invoice', False)
        ctx = invoice.sudo().action_invoice_sent()['context']
        composer = request.env['mail.compose.message'].with_context(**ctx).create({
            'composition_mode': 'comment' if len(invoice) == 1 else 'mass_mail',
            'template_id': template.id,
        })
        composer.sudo().onchange_template_id_wrapper()
        composer.sudo().send_mail()
        values = {
            'company': request.website.company_id,
            'user': request.env.user,
            'invoice': invoice,
        }
        return request.render('l10n_mx_portal.email_sent', values)

    @route(
        ['/generate_invoice/<int:order_id>', ],
        type='http', auth='user', website=True)
    def generate_invoice(self, order_id=None, **data):
        sale_obj = request.env['sale.order']
        sale = sale_obj.sudo().browse(order_id)
        if not sale.partner_id.vat:
            _message_post_helper(
                message=_('Please define your VAT, after try to generate the '
                          'invoice again.'), res_id=order_id,
                res_model='sale.order')
            return request.redirect(sale.get_portal_url())
        if sale.invoice_status != 'invoiced':
            invoice = sale._create_invoices()
            invoice.sudo().action_post()
            return request.redirect(sale.get_portal_url())
        reinvoice = sale.invoice_ids.l10n_mx_edi_action_reinvoice()
        if reinvoice:
            _message_post_helper(
                message=reinvoice, res_id=order_id, res_model='sale.order')
            return request.redirect(sale.get_portal_url())
        return request.redirect(sale.get_portal_url())


class PortalAccount(PA):

    @http.route(['/my/invoices/<model("account.invoice"):invoice>'], type='http', auth="public", website=True)
    def portal_my_invoice_detail(self, invoice, access_token=None, report_type=None, download=False, **kw):
        invoice_access = self._document_check_access('account.invoice', invoice.id, access_token)
        __import__('pdb').set_trace()
        pdf = invoice_access.get_cfdi_att(attachment_type='.pdf')
        if not pdf:
            self._show_report(
                model=invoice_access, report_type='pdf', report_ref='account.account_invoices', download=False)
        res = super(PortalAccount, self).portal_my_invoice_detail(
            invoice_id=invoice.id, access_token=access_token, report_type=report_type, download=download, **kw)
        return res
