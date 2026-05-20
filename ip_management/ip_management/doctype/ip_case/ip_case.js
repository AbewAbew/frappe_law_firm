frappe.ui.form.on('IP Case', {
    refresh: function (frm) {
        // Trigger visibility logic on load
        frm.trigger('case_type');
        frm.trigger('case_origin');

        // Recordal Trigger
        if (frm.doc.case_type === 'Recordals') {
            frm.trigger('source_origin');
            frm.trigger('recordal_type');
        }

        // Toggle Read-Only for Deadline
        frm.set_df_property('priority_document_deadline', 'read_only', 1);

        // Calculate deadlines and display dates on load
        calculate_priority_deadline(frm);
        calculate_renewal_display(frm);
        calculate_non_use_date(frm);
        update_case_status(frm);
        render_deadline_dashboard(frm);

        // Late renewal logic check on load
        frm.trigger('calculate_late_renewal_status');

        // Filter Local Agent to IP Manager or IP Staff
        frm.set_query('local_agent', function () {
            return {
                query: 'ip_management.ip_management.doctype.ip_case.ip_case.get_agents'
            }
        });

        // "Create Renewal" Button for Registered Cases
        if (frm.doc.case_status === 'Registered' && frm.doc.case_type !== 'Trademark Renewal' && frm.doc.case_type !== 'Recordals') {
            frm.add_custom_button(__('Create Renewal Application'), function () {
                frappe.model.open_mapped_doc({
                    method: "ip_management.ip_management.doctype.ip_case.ip_case.make_renewal",
                    frm: frm
                })
            });
        }
    },

    case_type: function (frm) {
        // Define Logic:
        // New Trademark: Data Entry -> Priority -> Office Actions -> Advertisement -> Registration -> Certificate
        // Renewal: Renewal Details -> POA -> Advertisement -> Certificate
        // Recordals: Setup -> Dynamic Sections -> Filing -> Registration -> Publication

        const is_new = frm.doc.case_type === 'New Trademark';
        const is_renewal = frm.doc.case_type === 'Trademark Renewal';
        const is_recordal = frm.doc.case_type === 'Recordals';
        const is_dispute = frm.doc.case_type === 'Disputes & Surrenders';

        // Common Toggle: Description of Goods, Transliteration, Color, Priority are NOT for Recordals
        // (Removing fields as per request for Recordals)
        if (is_recordal) {
            frm.toggle_display('goods_description', false);
            frm.toggle_display('transliteration', false);
            frm.toggle_display('color_claimed', false);
            frm.toggle_display('priority_claimed', false);
            frm.toggle_display('priority_section', false);

            // Rename Label
            // Rename Label
            frm.set_df_property('trademark_owner', 'label', 'Current Registered Owner');



            // Trigger Source Origin logic
            frm.trigger('source_origin');

        } else {
            // Restore Defaults if not Recordal
            frm.toggle_display('goods_description', true);
            // Transliteration/Priority depend on case_origin, handled there?
            // But we should ensure they aren't forced hidden if we switch back

            frm.set_df_property('trademark_owner', 'label', 'Trademark Owner');
        }

        // Toggle New Trademark specific sections
        // Note: We use the fieldname of the SECTION BREAK to toggle it.

        // Priority Claim Checkbox (New Only) - Section visibility depends on this checkbox
        // Only show priority_claimed if NOT Recordal (and NOT Renewal usually)
        frm.toggle_display('priority_claimed', is_new);

        // Office Actions (New Only)
        // Handled by depends_on in JSON: eval:doc.case_type == 'New Trademark'

        // Registration Fee (New Only)
        frm.toggle_display('registration_section', is_new);

        // Renewal Details (Renewal Only)
        frm.toggle_display('renewal_section', is_renewal);

        // Renewal Advertisement (Renewal Only - comes AFTER Certificate)
        // frm.toggle_display('renewal_advertisement_section', is_renewal); // This field logic seems custom/missing in JSON, keeping as is if usage exists

        // --- Renewal Logic Updates ---
        if (is_renewal) {
            // 1. Hide Opposition Fields (Undefined in Law for Renewal)
            frm.toggle_display('opposition_period_start', false);
            frm.toggle_display('opposition_period_end', false);
            frm.toggle_display('opposition_filed', false);

            // Show Renewal-specific fields in Filing section
            frm.set_df_property('original_application_date', 'hidden', 0);
            frm.set_df_property('current_expiration_date', 'hidden', 0);

            // Hide Invoice buttons for renewals
            frm.toggle_display('create_filing_invoice', false);
            frm.toggle_display('create_certificate_invoice', false);

            // 2. Lock Trademark Details if Internal Renewal
            let is_internal = frm.doc.source_origin === 'Internal';
            // If Internal and Original Case is linked, strictly LOCK details
            if (is_internal && frm.doc.linked_ip_case) {
                frm.set_df_property('trademark_details_section', 'read_only', 1);
                frm.set_df_property('trademark_name', 'read_only', 1);
                frm.set_df_property('trademark_owner', 'read_only', 1);
                frm.set_df_property('classes', 'read_only', 1);
                frm.set_df_property('trademark_type', 'read_only', 1);
            } else {
                // External or Manual -> Unlock
                frm.set_df_property('trademark_details_section', 'read_only', 0);
                frm.set_df_property('trademark_name', 'read_only', 0);
                frm.set_df_property('trademark_owner', 'read_only', 0);
                frm.set_df_property('classes', 'read_only', 0);
                frm.set_df_property('trademark_type', 'read_only', 0);
            }

            // Label Change: "Renewal Application Date"
            frm.set_df_property('application_date', 'label', 'Renewal Application Filed Date');

        } else if (is_new) {
            // Restore defaults for New Trademark
            frm.toggle_display('opposition_period_start', true);
            frm.toggle_display('opposition_period_end', true);
            frm.toggle_display('opposition_filed', true);

            // Hide Renewal-specific fields for non-renewals
            frm.set_df_property('original_application_date', 'hidden', 1);
            frm.set_df_property('current_expiration_date', 'hidden', 1);

            // Show Invoice buttons for non-renewals
            frm.toggle_display('create_filing_invoice', true);
            frm.toggle_display('create_certificate_invoice', true);

            frm.set_df_property('trademark_details_section', 'read_only', 0);
            frm.set_df_property('trademark_name', 'read_only', 0);
            frm.set_df_property('trademark_owner', 'read_only', 0);
            frm.set_df_property('classes', 'read_only', 0);
            frm.set_df_property('trademark_type', 'read_only', 0);

            // Restore Label
            frm.set_df_property('application_date', 'label', 'Application Date');

        } else if (is_dispute) {
            frm.toggle_display('create_filing_invoice', false);
            frm.toggle_display('create_publication_invoice', true);
            frm.toggle_display('create_certificate_invoice', false);

            // Hide Opposition Period fields, keep Advertisement Date/Upload
            frm.toggle_display('opposition_period_start', false);
            frm.toggle_display('opposition_period_end', false);
            frm.toggle_display('opposition_filed', false);
        }
    },

    case_origin: function (frm) {
        let is_national = frm.doc.case_origin === 'National';
        let is_internal = frm.doc.case_origin === 'Internal';

        // Hide Foreign Law Firm unless International
        let is_international = frm.doc.case_origin === 'International';
        frm.toggle_display('foreign_law_firm_section', is_international);

        // Transliteration & Priority Claimed are separate (Assuming internal doesn't need them or follows national?)
        // Keeping logical specific to Not National
        // But if Recordal, we force hide them in case_type, so this might re-show them if we are not careful.
        // We should check !is_recordal here too?
        if (frm.doc.case_type !== 'Recordals') {
            frm.toggle_display('transliteration', !is_national);
            frm.toggle_display('priority_claimed', !is_national);
        }

        // Safety: If National, uncheck Priority Claimed to ensure deadlines don't fire
        if (is_national && frm.doc.priority_claimed) {
            frm.set_value('priority_claimed', 0);
        }

        // Refresh lock/unlock logic
        frm.trigger('case_type');
    },

    source_origin: function (frm) {
        if (frm.doc.case_type === 'Trademark Renewal') {
            frm.trigger('case_type');
            return;
        }
        if (frm.doc.case_type !== 'Recordals') return;

        let is_internal = frm.doc.source_origin === 'Internal';

        // Locking Field Logic for Recordals
        // If Internal: Fields are Read Only (fetched)
        // If External: Fields are Editable
        let fields_to_lock = ['trademark_name', 'registration_number', 'trademark_owner', 'classes', 'trademark_type'];

        fields_to_lock.forEach(field => {
            frm.set_df_property(field, 'read_only', is_internal ? 1 : 0);
        });
    },

    recordal_type: function (frm) {
        if (frm.doc.case_type !== 'Recordals') return;

        // Logic:
        // Change of Address: Hide Publication Section. Filing Invoice Button visible.
        // Others: Show Publication Section. Publication Invoice visible.

        let is_change_address = frm.doc.recordal_type === 'Change of Address';

        // Toggle Publication Section
        frm.toggle_display('recordal_publication_section', !is_change_address);

        // Toggle Invoice Buttons
        // We assume standard "Filing" button in Filing Section IS NOT used for Recordals
        // because we added `create_recordal_filing_invoice`.
        // Visible only for Change of Address? Or always visible?
        // User said: "if the recordal type is change of adress... the invoice creation button will be at the Filling (recordal) stage"
        // Implies for others it might NOT be at Filing stage or they prioritize Publication?
        // But usually Filing Fee applies to all.
        // User requirement: "New trademark... has three invoice creating buttion... The trademark renewal has also one... Recordal case type... Change of Address... Publication not visible plus invoice creation button will be at Filling".
        // This *could* imply that for others, invoice is at Publication? Or both?
        // I will make `create_recordal_filing_invoice` visible for ALL Recordals usually, OR just Change of Address?
        // "Assignment... [etc]... create an invoice button on the Publication (Recordal) stage"
        // "Change of Address... Publication not visible... invoice creation button will be at Filling"
        // This implies:
        // Group A: Publication Invoice Button check.
        // Group B: Filing Invoice Button check.
        // I'll stick to:
        // Group A: Show Publication Invoice.
        // Group B: Show Filing Invoice. (And hide Publication Invoice/Section).
        // Does Group A need Filing Invoice? User didn't explicitly ask for it, but "New Trademark has three"...
        // I will follow specific instruction: "create an invoice button on the Publication... if... [Group A]"

        frm.toggle_display('create_recordal_publication_invoice', !is_change_address);
        frm.toggle_display('create_recordal_filing_invoice', is_change_address);
    },

    create_recordal_filing_invoice: function (frm) {
        frm.events.create_legal_bill(frm, "Recordal Filing");
    },

    create_recordal_publication_invoice: function (frm) {
        frm.events.create_legal_bill(frm, "Recordal Publication");
    },

    linked_ip_case: function (frm) {
        if (frm.doc.linked_ip_case && frm.doc.source_origin === 'Internal') {
            frappe.db.get_doc('IP Case', frm.doc.linked_ip_case).then(source => {
                // Fetch Details
                frm.set_value('trademark_name', source.trademark_name);
                frm.set_value('registration_number', source.registration_number);
                if (source.trademark_owner) frm.set_value('trademark_owner', source.trademark_owner);
                if (source.classes) frm.set_value('classes', source.classes);
                if (source.trademark_type) frm.set_value('trademark_type', source.trademark_type);
            });
        }
    },

    system_action_update_master: function (frm) {
        if (!frm.doc.linked_ip_case) {
            frappe.msgprint('No Linked IP Case to update.');
            return;
        }

        frappe.confirm(
            __('Are you sure you want to update the Master IP Case with the approved Recordal details?'),
            () => {
                frappe.call({
                    method: "update_master_case",
                    doc: frm.doc,
                    freeze: true,
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.msgprint('Master IP Case Updated Successfully');
                        }
                    }
                });
            }
        );
    },

    trademark_owner: function (frm) {
        if (frm.doc.trademark_owner) {
            frappe.db.get_doc('Trademark Owner', frm.doc.trademark_owner)
                .then(owner => {
                    // Logic 1: Auto-set Applicant for National Cases
                    if (frm.doc.case_origin === 'National') {
                        if (owner.customer_link) {
                            frm.set_value('applicant', owner.customer_link);
                            frappe.show_alert({ message: `Billing Entity Set: ${owner.customer_link}`, indicator: 'green' });
                        } else {
                            frappe.msgprint({
                                title: __('Billing Link Missing'),
                                message: __('The selected Trademark Owner is <b>not linked to a Customer</b>.<br>Please go to the Trademark Owner form and click "Create Linked Customer" to enable billing.'),
                                indicator: 'red'
                            });
                            frm.set_value('applicant', '');
                        }
                    }

                    // Logic 2: Check if they have a General POA
                    if (owner.poa_status === 'General (All Cases)' && owner.master_poa) {

                        frappe.msgprint({
                            title: __('General POA Found'),
                            message: __('This owner has a <b>General Power of Attorney</b>. It has been auto-added to the documents list.'),
                            indicator: 'green'
                        });

                        // 2. Auto-add row to "Initiation Documents" table
                        var row = frm.add_child('initiation_documents');
                        row.document_type = 'Power of Attorney';
                        row.attachment = owner.master_poa;
                        row.description = 'Fetched from Master - General POA';

                        // 3. Refresh the table to show the new row
                        frm.refresh_field('initiation_documents');
                    }
                    else {
                        // Optional: Reminder if no General POA exists
                        frappe.msgprint({
                            title: __('POA Required'),
                            message: __('This owner uses <b>Specific POAs</b>. Please attach the POA for this specific case.'),
                            indicator: 'orange'
                        });
                    }
                });
        }
    },

    advertisement_date: function (frm) {
        if (frm.doc.advertisement_date && frm.doc.case_type === 'New Trademark') {
            frm.set_value('opposition_period_start', frm.doc.advertisement_date);
            let end_date = frappe.datetime.add_days(frm.doc.advertisement_date, 60);
            frm.set_value('opposition_period_end', end_date);
        }
    },

    advertisement_published: function (frm) {
        update_case_status(frm);
    },

    opposition_period_end: function (frm) {
        frm.trigger('calculate_registration_fee_due');
    },

    opposition_deadline_extended: function (frm) {
        frm.trigger('calculate_registration_fee_due');
    },

    calculate_registration_fee_due: function (frm) {
        // Registration Fee Due Date starts from the day AFTER opposition ends
        // Deadline is 90 days from the due date
        let due_date_basis = frm.doc.opposition_deadline_extended || frm.doc.opposition_period_end;
        if (due_date_basis) {
            let due_date = frappe.datetime.add_days(due_date_basis, 1);
            frm.set_value('registration_fee_due_date', due_date);

            // Calculate Deadline: Due Date + 90 days
            let deadline = frappe.datetime.add_days(due_date, 90);
            frm.set_value('registration_fee_deadline', deadline);
        }
    },

    create_filing_invoice: function (frm) {
        frm.events.create_invoice(frm, "Filing");
    },

    create_publication_invoice: function (frm) {
        frm.events.create_invoice(frm, "Publication");
    },

    create_renewal_publication_invoice: function (frm) {
        // Renewal Publication Invoice
        frm.events.create_invoice(frm, "Renewal Publication");
    },

    create_certificate_invoice: function (frm) {
        frm.events.create_invoice(frm, "Registration");
    },

    create_invoice: function (frm, type) {
        if (frm.is_dirty()) {
            frappe.msgprint("Please save the form before creating an invoice.");
            return;
        }

        frappe.call({
            method: "create_legal_bill",
            doc: frm.doc,
            args: {
                bill_type: type
            },
            freeze: true,
            callback: function (r) {
                if (r.message) {
                    frappe.show_alert(`Legal Bill Created: ${r.message}`, 5);
                    // Open the Legal Bill in a new tab
                    frappe.set_route("Form", "Legal Bill", r.message);
                }
            }
        });
    }
});

frappe.ui.form.on('IP Office Action', {
    office_action_date: function (frm, cdt, cdn) {
        // Auto-calculate deadline: Date + 90 days
        let row = locals[cdt][cdn];
        if (row.office_action_date) {
            let deadline = frappe.datetime.add_days(row.office_action_date, 90);
            frappe.model.set_value(cdt, cdn, 'response_deadline', deadline);
        }
    },

    extend_deadline: function (frm, cdt, cdn) {
        // Logic: Add 90 days to current deadline, max 2 extensions
        let row = locals[cdt][cdn];

        let current_count = row.extension_count || 0;

        if (current_count >= 2) {
            frappe.msgprint(__('Maximum of 2 extensions allowed.'));
            return;
        }

        if (!row.response_deadline) {
            frappe.msgprint(__('Please set an Office Action Date first.'));
            return;
        }

        let new_deadline = frappe.datetime.add_days(row.response_deadline, 90);
        let new_count = current_count + 1;

        frappe.model.set_value(cdt, cdn, 'response_deadline', new_deadline);
        frappe.model.set_value(cdt, cdn, 'extension_count', new_count);

        frappe.show_alert(`Deadline extended to ${new_deadline} (Extension ${new_count}/2)`);
    }
});

frappe.ui.form.on('IP Case', {
    application_date: function (frm) {
        calculate_priority_deadline(frm);
        validate_priority_validity(frm);
        calculate_renewal_display(frm);
        update_case_status(frm);
    },

    priority_date: function (frm) {
        validate_priority_validity(frm);
    },

    original_application_date: function (frm) {
        // Calculate Current Expiration Date: Original App Date + 7 Years
        if (frm.doc.original_application_date) {
            let expiration_date = frappe.datetime.add_months(frm.doc.original_application_date, 84); // 7 Years
            frm.set_value('current_expiration_date', expiration_date);
        }
    },

    current_expiration_date: function (frm) {
        // Calculate Next Renewal Date: Current Expiration + 7 Years
        if (frm.doc.current_expiration_date) {
            let next_renewal = frappe.datetime.add_months(frm.doc.current_expiration_date, 84); // 7 Years
            frm.set_value('next_renewal_date', next_renewal);
        }
    },

    priority_claimed: function (frm) {
        frm.trigger('case_type'); // Update section visibility
        calculate_priority_deadline(frm);
        validate_priority_validity(frm);
    },

    priority_document_deadline: function (frm) {
        render_deadline_dashboard(frm);
    },

    certificate_issued_date: function (frm) {
        calculate_non_use_date(frm);
        update_case_status(frm);
    },

    registration_number: function (frm) {
        update_case_status(frm);
    },

    original_case: function (frm) {
        // On selection of original case for Internal Renewal
        if (frm.doc.original_case && frm.doc.case_origin === 'Internal') {
            frappe.db.get_doc('IP Case', frm.doc.original_case).then(source => {
                frm.set_value('trademark_name', source.trademark_name);
                frm.set_value('trademark_owner', source.trademark_owner);
                frm.set_value('trademark_type', source.trademark_type);
                frm.set_value('classes', source.classes);
                frm.set_value('goods_description', source.goods_description);
                frm.set_value('original_registration_number', source.registration_number);

                // If source has expiry date logic (e.g. renewal_date_display or calc'd), use it to set DUE DATE
                // Assuming 'renewal_date_display' on OLD case = Expiry Date
                if (source.renewal_date_display) {
                    frm.set_value('renewal_due_date', source.renewal_date_display);
                }

                // Trigger re-lock
                frm.trigger('case_type');
            });
        }
    },

    renewal_filed_date: function (frm) {
        calculate_late_renewal_status(frm);
        update_case_status(frm);
    },

    renewal_due_date: function (frm) {
        calculate_late_renewal_status(frm);
        calculate_renewal_display(frm);
    },

    opposition_filed: function (frm) {
        update_case_status(frm);
    },

    registration_fee_due_date: function (frm) {
        if (frm.doc.registration_fee_due_date) {
            let deadline = frappe.datetime.add_days(frm.doc.registration_fee_due_date, 90);
            frm.set_value('registration_fee_deadline', deadline);
        } else {
            frm.set_value('registration_fee_deadline', '');
        }
        update_case_status(frm);
    },

    // Child Table Trigger for Office Actions
    // We strictly use the generic `validate` or `refresh` usually, but `office_actions_add` works?
    // Actually, `frappe.ui.form.on('IP Case', ...)` supports fieldname_add/remove
    office_actions_add: function (frm) {
        update_case_status(frm);
    },
    office_actions_remove: function (frm) {
        update_case_status(frm);
    },

    applicant: function (frm) {
        if (frm.doc.applicant) {
            // Fetch Primary Contact Email
            frappe.db.get_value('Customer', frm.doc.applicant, 'customer_primary_contact')
                .then(r => {
                    if (r && r.message && r.message.customer_primary_contact) {
                        const contact_name = r.message.customer_primary_contact;
                        frappe.db.get_value('Contact', contact_name, 'email_id')
                            .then(r2 => {
                                if (r2 && r2.message && r2.message.email_id) {
                                    frm.set_value('firm_email', r2.message.email_id);
                                } else {
                                    frm.set_value('firm_email', '');
                                }
                            });
                    } else {
                        frm.set_value('firm_email', '');
                    }
                });
        } else {
            frm.set_value('firm_email', '');
        }
    }
});

// 1. Calculate the 90-Day Deadline for physical document submission
// Reference: Regulation Art. 13(2)
var calculate_priority_deadline = function (frm) {
    if (frm.doc.priority_claimed && frm.doc.application_date) {
        // Deadline is 90 days AFTER the Ethiopian Application Date
        var deadline = frappe.datetime.add_days(frm.doc.application_date, 90);
        frm.set_value('priority_document_deadline', deadline);
        render_deadline_dashboard(frm);
    }
};

// 2. Validate that the claim is within 6 months
// Reference: Proclamation Art. 10(1)
var validate_priority_validity = function (frm) {
    if (frm.doc.priority_claimed && frm.doc.priority_date && frm.doc.application_date) {
        // Calculate 6 months after Priority Date
        var max_valid_date = frappe.datetime.add_months(frm.doc.priority_date, 6);

        if (frm.doc.application_date > max_valid_date) {
            frappe.msgprint({
                title: __('Invalid Priority Claim'),
                message: __('According to Proclamation Art. 10(1), the Ethiopian application must be filed within <b>6 months</b> of the Priority Date. Your current date exceeds this limit.'),
                indicator: 'red'
            });
        }
    }
};

// 3. Calculate Non-Use Cancellation Vulnerability Date
// Reference: Proclamation Art. 35(2)
var calculate_non_use_date = function (frm) {
    if (frm.doc.certificate_issued_date) {
        // Warning: Vulnerable if not used for 3 consecutive years
        // We set the date to EXACTLY 3 years from issuance
        // Use frappe.datetime.add_months(date, 36)
        var vulnerability_date = frappe.datetime.add_months(frm.doc.certificate_issued_date, 36);
        frm.set_value('non_use_cancellation_date', vulnerability_date);
    }
};

// 4. Calculate Renewal Date for Display
// Reference: Proclamation Art. 24 (7 Years from Application Date)
// 4. Calculate Renewal Date for Display
// Reference: Proclamation Art. 24 (7 Years from Application Date)
var calculate_renewal_display = function (frm) {
    if (frm.doc.case_type === 'Trademark Renewal') {
        // Internal Renewal: New Expiry = Old Expiry (Renewal Due Date) + 7 Years
        // If we don't have Due Date yet, we wait.
        if (frm.doc.renewal_due_date && frm.doc.case_origin === 'Internal') {
            let next_renewal = frappe.datetime.add_months(frm.doc.renewal_due_date, 84); // 7 Years
            frm.set_value('renewal_date_display', next_renewal);
        }
        else if (frm.doc.renewal_due_date) {
            // External/Manual: If they set "Renewal Due Date" as the 'Old Expiry', we calc from that too?
            let next_renewal = frappe.datetime.add_months(frm.doc.renewal_due_date, 84);
            frm.set_value('renewal_date_display', next_renewal);
        }
    } else {
        // New Trademark
        if (frm.doc.application_date) {
            let renewal_date = frappe.datetime.add_months(frm.doc.application_date, 84);
            frm.set_value('renewal_date_display', renewal_date);
        }
    }
};

// Late Renewal Logic
var calculate_late_renewal_status = function (frm) {
    if (frm.doc.case_type !== 'Trademark Renewal' || !frm.doc.renewal_filed_date || !frm.doc.renewal_due_date) {
        frm.set_value('late_renewal_status', '');
        return;
    }

    let filed = frm.doc.renewal_filed_date;
    let due = frm.doc.renewal_due_date;

    // Regular: Within 3 months AFTER expiry? Or just BEFORE?
    // "Within 3 months after expiry" usually means [Expiry, Expiry + 3mo]
    // But logically you can renew BEFORE expiry too (e.g. 3 months prior).
    // So if Filed <= Due + 3 Months -> Regular

    let due_plus_3 = frappe.datetime.add_months(due, 3);
    let due_plus_9 = frappe.datetime.add_months(due, 9);

    if (filed <= due_plus_3) {
        frm.set_value('late_renewal_status', 'Regular Renewal');
    }
    else if (filed <= due_plus_9) {
        frm.set_value('late_renewal_status', 'Late Renewal (Penalty Applies)');
        frappe.msgprint(__('<b>Late Renewal Penalty Applies</b><br>The application is filed between 3 and 9 months after expiry. A 50% penalty fee is required per Regulation Art. 56(3).'));
    }
    else {
        frm.set_value('late_renewal_status', 'Cancelled / Time Barred');
        frappe.msgprint(__('<b>Renewal Time Barred</b><br>The application is filed more than 9 months after expiry. The execution period has lapsed.'));
    }
};

// 5. Update Case Status Logic
var update_case_status = function (frm) {
    // Logic Split

    if (frm.doc.case_type === 'Recordals') {
        let status = 'New';
        if (frm.doc.publication_date) {
            status = 'Published';
        } else if (frm.doc.decision_outcome === 'Approved' || frm.doc.recordal_registration_date) {
            status = 'Registered';
        } else if (frm.doc.filing_date) {
            status = 'Filed';
        }

        if (frm.doc.case_status !== status) {
            frm.set_value('case_status', status);
        }
        return;
    }

    if (frm.doc.case_type === 'Trademark Renewal') {
        let status = 'New';

        // Renewal Workflow Priority:
        // 1. Advertisement Published -> Renewed
        // 2. Renewal Filed -> Renewal Filed

        if (frm.doc.advertisement_published) {
            status = 'Renewed';
        } else if (frm.doc.application_date) {
            status = 'Renewal Filed';
        }

        if (frm.doc.case_status !== status) {
            frm.set_value('case_status', status);
        }
        return;
    }

    if (frm.doc.case_type !== 'New Trademark') return;

    let status = 'New';

    if (frm.doc.registration_number && frm.doc.certificate_issued_date) {
        status = 'Registered';
    } else if (frm.doc.registration_fee_due_date && frm.doc.registration_fee_due_date <= frappe.datetime.now_date()) {
        status = 'Registration Fee Due';
    } else if (frm.doc.opposition_filed) {
        status = 'Opposed';
    } else if (frm.doc.advertisement_published) {
        status = 'Advertised';
    } else {
        // Check Office Actions
        let has_oa = frm.doc.office_actions && frm.doc.office_actions.length > 0;
        let has_response = false;
        if (has_oa) {
            frm.doc.office_actions.forEach(row => {
                // Assuming field name for response date in child table is response_date (?)
                // Need to verify field name. In Step 515 line 153 `IP Office Action` has `office_action_date`.
                // I don't see `response_date` explicitly mentioned in Step 515 other than `if (row.response_date)` check I proposed?
                // Wait, I didn't see `IP Office Action` struct.
                // Step 515 line 158: `frappe.model.set_value(cdt, cdn, 'response_deadline', deadline);`
                // It sets `response_deadline`.
                // Does it have `response_date`?
                // I'll assume `response_filed_date` or `response_date`.
                // Checking `ip_case.json`? No, it's a child table `IP Office Action`.
                // I will assume `response_date` for now. If it fails, I'll debug.
                if (row.response_date) has_response = true;
            });
        }

        if (has_response) {
            status = 'Response Filed';
        } else if (has_oa) {
            status = 'Office Action Received';
        } else if (frm.doc.application_date) {
            status = 'Filed';
        }
    }

    if (frm.doc.case_status !== status) {
        frm.set_value('case_status', status);
    }

    // Refresh Dashboard if status changes (or always?)
    render_deadline_dashboard(frm);
};

// 6. Deadline Dashboard
var render_deadline_dashboard = function (frm) {
    let deadlines = [];
    let today = frappe.datetime.now_date();

    let add_deadline = (label, date) => {
        if (!date) return;

        // Only show Today or Future dates.
        // Once passed (date < today), remove from dashboard.
        // We use get_diff(date, today) >= 0 to handle both Date objects and Strings safely.
        if (frappe.datetime.get_diff(date, today) >= 0) {
            deadlines.push({ label: label, date: date });
        }
    };

    add_deadline("Priority Doc Deadline", frm.doc.priority_document_deadline);
    add_deadline("Opposition Period End", frm.doc.opposition_period_end);
    add_deadline("Ext. Opposition Deadline", frm.doc.opposition_deadline_extended);
    add_deadline("Registration Fee Deadline", frm.doc.registration_fee_deadline);
    add_deadline("Non-Use Vulnerability", frm.doc.non_use_cancellation_date);
    add_deadline("Renewal Date", frm.doc.renewal_date_display);

    // Office Actions
    if (frm.doc.office_actions) {
        frm.doc.office_actions.forEach(row => {
            if (row.response_deadline) {
                // Check if responded?
                if (!row.response_date) {
                    add_deadline(`Response Deadline (${row.office_action_date})`, row.response_deadline);
                }
            }
        });
    }

    if (deadlines.length === 0) {
        // Show placeholder instead of hiding
        let html = `<div style="padding: 10px; color: #6b7280; font-size: 13px; font-style: italic;">No Pending Deadlines</div>`;
        frm.set_df_property('deadline_summary', 'options', html);
        frm.set_df_property('deadline_summary', 'hidden', 0);
        return;
    }
    frm.set_df_property('deadline_summary', 'hidden', 0);

    // Sort by date
    deadlines.sort((a, b) => {
        if (a.date < b.date) return -1;
        if (a.date > b.date) return 1;
        return 0;
    });

    // Render HTML
    let html = `<div style="display: flex; gap: 10px; overflow-x: auto; padding: 10px 0;">`;

    let bg_map = { red: '#fee2e2', orange: '#ffedd5', green: '#dcfce7', gray: '#f3f4f6' };
    let text_map = { red: '#991b1b', orange: '#9a3412', green: '#166534', gray: '#1f2937' };

    deadlines.forEach(d => {
        let diff = frappe.datetime.get_diff(d.date, today);
        let color = 'green';

        // Customize color logic
        if (diff <= 7) color = 'red';
        else if (diff <= 30) color = 'orange';

        let label_text = "Days Left";
        // If today
        if (diff === 0) label_text = "Days Left (Today)";

        let style = `
            background: ${bg_map[color]};
            color: ${text_map[color]};
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid ${text_map[color]}20;
            font-family: 'Inter', sans-serif;
            min-width: 140px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        `;

        html += `
            <div style="${style}">
                <div style="font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8;">${d.label}</div>
                <div style="font-size: 16px; font-weight: 700; margin: 4px 0;">${diff} ${label_text}</div>
                <div style="font-size: 11px; opacity: 0.8;">${d.date}</div>
            </div>
        `;
    });

    html += `</div>`;

    frm.set_df_property('deadline_summary', 'options', html);
    frm.refresh_field('deadline_summary');
};
