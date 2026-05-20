// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Patent Application', {
    refresh: function (frm) {
        frm.trigger('toggle_fields');
    },

    application_type: function (frm) {
        frm.trigger('toggle_fields');
    },

    applicant_is_inventor: function (frm) {
        frm.trigger('toggle_fields');
    },

    filing_date: function (frm) {
        if (frm.doc.filing_date) {
            // Auto calculate priority deadline (12 months)
            var priority_deadline = frappe.datetime.add_months(frm.doc.filing_date, 12);
            frm.set_value('priority_deadline', priority_deadline);
        }
    },

    toggle_fields: function (frm) {
        // Industrial Design specifics
        if (frm.doc.application_type == 'Industrial Design') {
            frm.set_df_property('specimen_submitted', 'hidden', 0);
            frm.set_df_property('graphic_representations', 'hidden', 0);
            frm.set_df_property('product_class', 'hidden', 0);
        } else {
            frm.set_df_property('specimen_submitted', 'hidden', 1);
            frm.set_df_property('graphic_representations', 'hidden', 1);
            frm.set_df_property('product_class', 'hidden', 1);
        }
    }
});
