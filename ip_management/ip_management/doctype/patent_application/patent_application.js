// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

const PATENT_STATUS_TRANSITIONS = {
    'Draft': ['Filed', 'Withdrawn'],
    'Filed': ['Formal Exam', 'Refused', 'Withdrawn'],
    'Formal Exam': ['Substantive Exam', 'Refused', 'Withdrawn'],
    'Substantive Exam': ['Published', 'Refused', 'Withdrawn'],
    'Published': ['Granted', 'Refused', 'Withdrawn'],
    'Granted': ['Surrendered', 'Expired']
};

function can_transition_patent_status() {
    return frappe.session.user === 'Administrator'
        || ['IP Manager', 'System Manager'].some(role => frappe.user_roles.includes(role));
}

frappe.ui.form.on('Patent Application', {
    refresh: function (frm) {
        frm.trigger('toggle_fields');
        frm.trigger('add_status_actions');
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
    },

    add_status_actions: function (frm) {
        if (frm.is_new() || !can_transition_patent_status()) {
            return;
        }

        (PATENT_STATUS_TRANSITIONS[frm.doc.status] || []).forEach(new_status => {
            frm.add_custom_button(__(new_status), function () {
                if (frm.is_dirty()) {
                    frappe.msgprint(__('Save your changes before changing status.'));
                    return;
                }

                frappe.confirm(
                    __('Change status from {0} to {1}?', [frm.doc.status, new_status]),
                    () => {
                        frm.call({
                            method: 'transition_status',
                            doc: frm.doc,
                            args: { new_status: new_status },
                            freeze: true,
                            freeze_message: __('Changing status')
                        }).then(() => frm.reload_doc());
                    }
                );
            }, __('Change Status'));
        });
    }
});
