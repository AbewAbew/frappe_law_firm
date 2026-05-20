# Copyright (c) 2025, Law Firm and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import nowdate, add_days, getdate, date_diff


def daily():
    """
    Daily scheduled task to check for upcoming deadlines and create reminder tasks.
    This runs automatically every day via Frappe's scheduler.
    """
    check_office_action_deadlines()
    check_opposition_period_deadlines()
    check_registration_fee_deadlines()
    check_renewal_deadlines()


def check_office_action_deadlines(days_before=7):
    """
    Check for office action response deadlines approaching within the specified days.
    Creates an IP Task if a reminder hasn't been created yet.
    """
    target_date = add_days(nowdate(), days_before)

    # Get all IP Cases with office actions that have upcoming response deadlines
    office_actions = frappe.db.sql("""
        SELECT
            oa.response_deadline,
            oa.action_type,
            oa.parent as ip_case,
            ipc.trademark_name,
            ipc.name as case_name,
            ipc.application_number
        FROM `tabIP Office Action` oa
        JOIN `tabIP Case` ipc ON oa.parent = ipc.name
        WHERE oa.response_deadline BETWEEN %s AND %s
        AND oa.response_filed = 0
        AND NOT EXISTS (
            SELECT 1 FROM `tabIP Task` t
            WHERE t.ip_case = oa.parent
            AND t.subject LIKE '%%Office Action Response%%'
            AND t.due_date = oa.response_deadline
            AND t.status = 'Open'
        )
    """, (nowdate(), target_date), as_dict=True)

    for oa in office_actions:
        create_reminder_task(
            ip_case=oa.ip_case,
            subject=f"Office Action Response Due: {oa.trademark_name} ({oa.application_number or oa.case_name})",
            due_date=oa.response_deadline,
            description=f"Response deadline for office action ({oa.action_type or 'N/A'}) is approaching."
        )


def check_opposition_period_deadlines(days_before=7):
    """
    Check for opposition period end dates approaching.
    """
    target_date = add_days(nowdate(), days_before)

    cases = frappe.db.sql("""
        SELECT
            name,
            application_number,
            trademark_name,
            opposition_period_end
        FROM `tabIP Case`
        WHERE opposition_period_end BETWEEN %s AND %s
        AND advertisement_published = 1
        AND opposition_filed = 0
        AND NOT EXISTS (
            SELECT 1 FROM `tabIP Task` t
            WHERE t.ip_case = `tabIP Case`.name
            AND t.subject LIKE '%%Opposition Period Ending%%'
            AND t.status = 'Open'
        )
    """, (nowdate(), target_date), as_dict=True)

    for case in cases:
        create_reminder_task(
            ip_case=case.name,
            subject=f"Opposition Period Ending: {case.trademark_name} ({case.application_number or case.name})",
            due_date=case.opposition_period_end,
            description="The opposition period is ending soon. If no opposition is filed, proceed to registration."
        )


def check_registration_fee_deadlines(days_before=14):
    """
    Check for registration fee due dates approaching.
    """
    target_date = add_days(nowdate(), days_before)

    cases = frappe.db.sql("""
        SELECT
            name,
            application_number,
            trademark_name,
            registration_fee_due_date
        FROM `tabIP Case`
        WHERE registration_fee_due_date BETWEEN %s AND %s
        AND (payment_date IS NULL OR payment_date = '')
        AND NOT EXISTS (
            SELECT 1 FROM `tabIP Task` t
            WHERE t.ip_case = `tabIP Case`.name
            AND t.subject LIKE '%%Registration Fee Due%%'
            AND t.status = 'Open'
        )
    """, (nowdate(), target_date), as_dict=True)

    for case in cases:
        create_reminder_task(
            ip_case=case.name,
            subject=f"Registration Fee Due: {case.trademark_name} ({case.application_number or case.name})",
            due_date=case.registration_fee_due_date,
            description="Registration fee payment is due. Please process payment to EIPA."
        )


def check_renewal_deadlines(months_before=3):
    """
    Check for trademark renewal due dates approaching.
    Creates reminders for trademarks due for renewal within the specified months.
    """
    days_before = months_before * 30  # Approximate
    target_date = add_days(nowdate(), days_before)

    cases = frappe.db.sql("""
        SELECT
            name,
            application_number,
            trademark_name,
            renewal_due_date,
            firm_name,
            firm_email
        FROM `tabIP Case`
        WHERE case_type = 'Trademark Renewal'
        AND renewal_due_date BETWEEN %s AND %s
        AND reminder_needed = 1
        AND (renewal_filed_date IS NULL OR renewal_filed_date = '')
        AND NOT EXISTS (
            SELECT 1 FROM `tabIP Task` t
            WHERE t.ip_case = `tabIP Case`.name
            AND t.subject LIKE '%%Renewal Due%%'
            AND t.status = 'Open'
        )
    """, (nowdate(), target_date), as_dict=True)

    for case in cases:
        days_until_due = date_diff(case.renewal_due_date, nowdate())
        create_reminder_task(
            ip_case=case.name,
            subject=f"Renewal Due in {days_until_due} days: {case.trademark_name} ({case.application_number or case.name})",
            due_date=case.renewal_due_date,
            description=f"Trademark renewal is due. Contact firm: {case.firm_name or 'N/A'} ({case.firm_email or 'N/A'})"
        )


def create_reminder_task(ip_case, subject, due_date, description=""):
    """
    Helper function to create an IP Task as a reminder.
    """
    task = frappe.get_doc({
        "doctype": "IP Task",
        "subject": subject,
        "ip_case": ip_case,
        "due_date": due_date,
        "status": "Open",
        "description": description,
        "assigned_to": "Administrator"
    })
    task.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.logger().info(f"Created reminder task: {subject}")
