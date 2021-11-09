from odoo import _, models, api, tools

try:
    from num2words import num2words
except ImportError:
    _logger.warning("The num2words python library is not installed, amount-to-text features won't be fully available.")
    num2words = None


class ResCurrency(models.Model):
    _inherit = "res.currency"

    #@api.multi
    def amount_to_text(self, amount):
        self.ensure_one()

        def _num2words(number, lang):
            try:
                return num2words(number, lang=lang).title()
            except NotImplementedError:
                return num2words(number, lang='en').title()

        if num2words is None:
            logging.getLogger(__name__).warning("The library 'num2words' is missing, cannot render textual amounts.")
            return ""

        formatted = "%.{0}f".format(self.decimal_places) % amount
        parts = formatted.partition('.')
        integer_value = int(parts[0])
        fractional_value = int(parts[2] or 0)

        lang_code = self.env.context.get('lang') or self.env.user.lang
        lang = self.env['res.lang'].with_context(active_test=False).search([('code', '=', lang_code)])
        amount_words = tools.ustr('{amt_value} {amt_word}').format(
            amt_value=_num2words(integer_value, lang=lang.iso_code),
            amt_word=self.currency_unit_label,
        )

        if fractional_value == 0:
            amount_words += ' 00/100 M.N.'

        if not self.is_zero(amount - integer_value):
            context = self._context
            params = context.get('params') if 'params' in context else False
            if params and 'model' in params and params.get('model') == 'account.payment' and \
                    'lang' in context and (context.get('lang') == 'es_MX' or context.get('lang') == 'es_ES'):
                amount_in_word = amount_words + ' ' + str(fractional_value) + '/100' + ' MN'
                amount_words = amount_in_word
            elif 'active_model' in context and context.get('active_model') == 'account.payment' \
                    and 'lang' in context and (context.get('lang') == 'es_MX' or context.get('lang') == 'es_ES'):
                amount_in_word = amount_words + ' ' + str(fractional_value) + '/100' + ' MN'
                amount_words = amount_in_word
            elif 'default_partner_type' in context and context.get('default_partner_type') == 'supplier' \
                    and 'lang' in context and (context.get('lang') == 'es_MX' or context.get('lang') == 'es_ES'):
                amount_in_word = amount_words + ' ' + str(fractional_value) + '/100' + ' MN'
                amount_words = amount_in_word
            else:
                amount_words += ' ' + _('and') + tools.ustr(' {amt_value} {amt_word}').format(
                    amt_value=_num2words(fractional_value, lang=lang.iso_code),
                    amt_word=self.currency_subunit_label,
                )

        return amount_words
