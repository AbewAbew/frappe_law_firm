frappe.ui.form.on('Trademark Owner', {
    refresh: function (frm) {
        if (!frm.doc.customer_link) {
            frm.add_custom_button(__('Create Linked Customer'), function () {
                frappe.confirm(
                    'Are you sure you want to create a Customer record for this Owner?',
                    function () {
                        frm.events.create_customer(frm);
                    }
                );
            });
        }
    },

    create_customer: function (frm) {
        let owner_type_map = {
            'Individual': 'Individual',
            'Company': 'Company',
            'Association': 'Company' // Map Association to Company for ERPNext
        };

        let new_customer = {
            doctype: 'Customer',
            customer_name: frm.doc.owner_name,
            customer_type: owner_type_map[frm.doc.owner_type] || 'Company',
            customer_group: 'All Customer Groups',
            territory: 'All Territories'
        };

        frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: new_customer
            },
            freeze: true,
            callback: function (r) {
                if (r.message) {
                    frappe.show_alert({
                        message: __('Customer Created: ' + r.message.name),
                        indicator: 'green'
                    });
                    frm.set_value('customer_link', r.message.name);
                    frm.save();
                }
            },
            error: function (r) {
                // If generic error (likely duplicate name), warn user
                frappe.msgprint(__('Could not create Customer. A Customer with this name might already exist. Please link it manually.'));
            }
        });
    }
});
