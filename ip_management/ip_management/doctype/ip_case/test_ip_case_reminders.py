import unittest
from unittest.mock import Mock, patch

import frappe

from ip_management.ip_management.doctype.ip_case import ip_case as ip_case_module
from ip_management.ip_management.doctype.ip_case.ip_case import (
	IP_CASE_DEADLINE_REMINDERS,
	daily_deadline_check,
	get_case_lead_email,
	match_deadline,
	should_send_case_deadline,
)


class TestIPCaseReminders(unittest.TestCase):
	def test_task_only_intervals_are_present_in_case_email_schedule(self):
		reminders = {
			fieldname: reminder_days
			for fieldname, _label, reminder_days in IP_CASE_DEADLINE_REMINDERS
		}

		self.assertEqual(reminders["registration_fee_due_date"], (14,))
		self.assertEqual(reminders["renewal_due_date"], (90,))

	def test_daily_check_covers_standard_moved_and_office_action_reminders(self):
		case = frappe._dict(
			name="TBeST/RW/26/00001",
			trademark_name="Test Mark",
			application_number="APP-001",
			local_agent="ip.manager@example.com",
			applicant="CUST-001",
			firm_email="client@example.com",
			case_type="Trademark Renewal",
			advertisement_published=1,
			opposition_filed=0,
			payment_date=None,
			reminder_needed=1,
			renewal_filed_date=None,
			priority_document_deadline="2026-08-16",
			registration_fee_deadline=None,
			non_use_cancellation_date=None,
			renewal_date_display=None,
			opposition_period_end=None,
			opposition_deadline_extended=None,
			registration_fee_due_date="2026-08-23",
			renewal_due_date="2026-11-07",
		)
		office_action = frappe._dict(
			office_action_date="2026-07-01",
			action_type="Clarification",
			response_deadline="2026-08-16",
			response_filed=0,
			response_date=None,
		)

		def get_all(doctype, **_kwargs):
			return [case] if doctype == "IP Case" else [office_action]

		with (
			patch.object(ip_case_module.frappe, "get_all", side_effect=get_all),
			patch.object(ip_case_module, "nowdate", return_value="2026-08-09"),
			patch.object(
				ip_case_module,
				"get_case_lead_email",
				return_value="ip.manager@example.com",
			),
			patch.object(ip_case_module, "send_deadline_email") as send_email,
		):
			daily_deadline_check()

		self.assertEqual(send_email.call_count, 4)
		calls_by_label = {email_call.args[2]: email_call.args for email_call in send_email.call_args_list}
		self.assertEqual(calls_by_label["Priority Document Deadline"][4], 7)
		self.assertEqual(calls_by_label["Registration Fee Due"][4], 14)
		self.assertEqual(calls_by_label["Trademark Renewal Due"][4], 90)
		self.assertIn("CUST-001", calls_by_label["Trademark Renewal Due"][5])
		self.assertEqual(calls_by_label["Office Action Response (2026-07-01)"][4], 7)
		self.assertIn("Clarification", calls_by_label["Office Action Response (2026-07-01)"][5])

	def test_completed_or_paid_stage_does_not_send_moved_reminder(self):
		case = frappe._dict(
			case_type="Trademark Renewal",
			advertisement_published=1,
			opposition_filed=0,
			payment_date="2026-08-01",
			reminder_needed=1,
			renewal_filed_date="2026-08-01",
		)

		self.assertFalse(should_send_case_deadline(case, "registration_fee_due_date"))
		self.assertFalse(should_send_case_deadline(case, "registration_fee_deadline"))
		self.assertFalse(should_send_case_deadline(case, "renewal_due_date"))

	def test_case_lead_email_requires_enabled_system_user(self):
		fake_db = Mock()
		fake_db.get_value.return_value = "ip.manager@example.com"

		with patch.object(frappe.local, "db", fake_db, create=True):
			email = get_case_lead_email("ip.manager@example.com")

		self.assertEqual(email, "ip.manager@example.com")
		self.assertEqual(
			fake_db.get_value.call_args.args[1],
			{
				"name": "ip.manager@example.com",
				"enabled": 1,
				"user_type": "System User",
			},
		)
		self.assertIsNone(get_case_lead_email("Administrator"))

	def test_match_deadline_sends_only_on_configured_day(self):
		case = frappe._dict(name="TBeST/NR/26/00001")

		with patch.object(ip_case_module, "send_deadline_email") as send_email:
			match_deadline(
				case,
				"Registration Fee Due",
				"2026-08-23",
				frappe.utils.getdate("2026-08-09"),
				(14,),
			)
			match_deadline(
				case,
				"Registration Fee Due",
				"2026-08-23",
				frappe.utils.getdate("2026-08-10"),
				(14,),
			)

		send_email.assert_called_once()

	def test_email_is_linked_to_ip_case(self):
		case = frappe._dict(
			name="TBeST/NR/26/00001",
			trademark_name="Test Mark",
			application_number="APP-001",
			case_lead_email="ip.manager@example.com",
		)

		with (
			patch.object(ip_case_module, "deadline_email_already_queued", return_value=False),
			patch.object(ip_case_module.frappe, "sendmail") as sendmail,
		):
			ip_case_module.send_deadline_email(
				case,
				"Upcoming Deadline (2 Weeks): Registration Fee Due",
				"Registration Fee Due",
				frappe.utils.getdate("2026-08-23"),
				14,
			)

		self.assertEqual(sendmail.call_args.kwargs["recipients"], ["ip.manager@example.com"])
		self.assertEqual(sendmail.call_args.kwargs["reference_doctype"], "IP Case")
		self.assertEqual(sendmail.call_args.kwargs["reference_name"], case.name)

	def test_duplicate_email_queue_is_not_created(self):
		case = frappe._dict(
			name="TBeST/NR/26/00001",
			trademark_name="Test Mark",
			application_number="APP-001",
			case_lead_email="ip.manager@example.com",
		)

		with (
			patch.object(ip_case_module, "deadline_email_already_queued", return_value=True),
			patch.object(ip_case_module.frappe, "sendmail") as sendmail,
		):
			ip_case_module.send_deadline_email(
				case,
				"Upcoming Deadline (2 Weeks): Registration Fee Due",
				"Registration Fee Due",
				frappe.utils.getdate("2026-08-23"),
				14,
			)

		sendmail.assert_not_called()


if __name__ == "__main__":
	unittest.main()
