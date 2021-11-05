def update_x_l10n_mx_edi_invoice_broker_id_model_data(cr):
    cr.execute("""
        SELECT
            id
        FROM ir_model_fields
        WHERE name='x_l10n_mx_edi_invoice_broker_id' AND model='account.move.line' LIMIT 1;
        """)
    invoice_broker_id_field_id = cr.fetchone()[0]
    if invoice_broker_id_field_id:
        cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id)
        VALUES ('field_account_invoice_l10n_mx_edi_invoice_broker_id',
                'l10n_mx_import_taxes', 'ir.model.fields', %s)""", [invoice_broker_id_field_id])


def migrate(cr, version):
    if not version:
        return
    update_x_l10n_mx_edi_invoice_broker_id_model_data(cr)
