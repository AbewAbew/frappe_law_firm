import unittest
from unittest.mock import Mock, patch

import frappe

from ip_management.ip_management.doctype.ip_case import ip_case as ip_case_module
from ip_management.ip_management.doctype.ip_case.ip_case import (
	DEFAULT_CURRENCY,
	IP_BILLING_STAGES,
	IPCase,
	can_create_ip_invoice,
	check_ip_invoice_creation_permission,
	get_case_currency,
	get_configured_billing_items,
	get_derived_case_status,
	make_renewal,
	set_case_deadlines,
)
from ip_management.ip_management.patches.v1_0.backfill_ip_invoice_sources import (
	_get_ip_billing_stage,
)


class TestIPCaseCurrency(unittest.TestCase):
	def test_server_calculates_fixed_stage_deadlines(self):
		case = frappe._dict(
			case_type="New Trademark",
			application_date="2026-01-01",
			priority_claimed=1,
			advertisement_date="2026-04-01",
			opposition_deadline_extended=None,
			registration_fee_due_date=None,
			certificate_issued_date="2026-08-01",
			original_application_date=None,
			current_expiration_date=None,
			renewal_due_date=None,
			renewal_filed_date=None,
			office_actions=[
				frappe._dict(office_action_date="2026-05-01", response_deadline=None),
			],
		)

		set_case_deadlines(case)

		self.assertEqual(str(case.priority_document_deadline), "2026-04-01")
		self.assertEqual(str(case.opposition_period_end), "2026-05-31")
		self.assertEqual(str(case.registration_fee_due_date), "2026-06-01")
		self.assertEqual(str(case.registration_fee_deadline), "2026-08-30")
		self.assertEqual(str(case.non_use_cancellation_date), "2029-08-01")
		self.assertEqual(str(case.renewal_date_display), "2033-01-01")
		self.assertEqual(str(case.office_actions[0].response_deadline), "2026-07-30")

	def test_server_preserves_extended_office_action_deadline(self):
		case = frappe._dict(
			case_type="Disputes & Surrenders",
			application_date=None,
			priority_claimed=0,
			advertisement_date=None,
			registration_fee_due_date=None,
			certificate_issued_date=None,
			original_application_date=None,
			current_expiration_date=None,
			renewal_due_date=None,
			renewal_filed_date=None,
			office_actions=[
				frappe._dict(
					office_action_date="2026-05-01",
					response_deadline="2026-10-28",
				),
			],
		)

		set_case_deadlines(case)

		self.assertEqual(case.office_actions[0].response_deadline, "2026-10-28")

	def test_server_derives_case_status_from_stage_data(self):
		new_case = frappe._dict(
			case_type="New Trademark",
			case_status="New",
			registration_number=None,
			certificate_issued_date=None,
			registration_fee_due_date=None,
			opposition_filed=0,
			advertisement_published=0,
			application_date="2026-01-01",
			office_actions=[],
		)
		renewal = frappe._dict(
			case_type="Trademark Renewal",
			advertisement_published=1,
			application_date="2026-01-01",
		)
		recordal = frappe._dict(
			case_type="Recordals",
			publication_date=None,
			decision_outcome="Approved",
			recordal_registration_date=None,
			filing_date="2026-01-01",
		)

		self.assertEqual(get_derived_case_status(new_case, "2026-08-08"), "Filed")
		self.assertEqual(get_derived_case_status(renewal, "2026-08-08"), "Renewed")
		self.assertEqual(get_derived_case_status(recordal, "2026-08-08"), "Registered")

	def test_only_ip_manager_and_system_manager_can_create_ip_invoices(self):
		with patch.object(ip_case_module.frappe, "get_roles", return_value=["IP Manager"]):
			self.assertTrue(can_create_ip_invoice("manager@example.com"))

		with patch.object(ip_case_module.frappe, "get_roles", return_value=["System Manager"]):
			self.assertTrue(can_create_ip_invoice("system@example.com"))

		with patch.object(ip_case_module.frappe, "get_roles", return_value=["IP Staff"]):
			self.assertFalse(can_create_ip_invoice("staff@example.com"))

		with patch.object(ip_case_module.frappe, "get_roles", return_value=["Legal Finance"]):
			self.assertFalse(can_create_ip_invoice("finance@example.com"))

	def test_ip_staff_invoice_request_is_rejected_server_side(self):
		with (
			patch.object(ip_case_module, "can_create_ip_invoice", return_value=False),
			patch.object(
				ip_case_module.frappe,
				"throw",
				side_effect=frappe.PermissionError("not permitted"),
			),
		):
			with self.assertRaises(frappe.PermissionError):
				check_ip_invoice_creation_permission("staff@example.com")

	def test_ip_invoice_backfill_recognizes_one_stage_only(self):
		filing_items = [
			frappe._dict(service="Trademark Filing Fee"),
			frappe._dict(service="Professional Fee - Filing"),
		]
		mixed_items = [*filing_items, frappe._dict(service="Trademark Registration Fee")]

		self.assertEqual(_get_ip_billing_stage(filing_items), "Filing")
		self.assertIsNone(_get_ip_billing_stage(mixed_items))
		self.assertIsNone(_get_ip_billing_stage([frappe._dict(service="Unrelated Service")]))

	def test_internal_renewal_sets_consistent_source_and_master_fields(self):
		source = frappe._dict(
			name="TBeST/NR/26/00001",
			currency="USD",
			trademark_name="Test Mark",
			trademark_owner="OWNER-001",
			classes="35",
			goods_description="Legal services",
			registration_number="REG-001",
		)
		target = frappe._dict()

		def fake_mapper(_doctype, _source_name, _mapping, _target_doc, callback):
			callback(source, target)
			return target

		with patch.object(ip_case_module, "get_mapped_doc", side_effect=fake_mapper):
			result = make_renewal(source.name)

		self.assertEqual(result.source_origin, "Internal")
		self.assertEqual(result.linked_ip_case, source.name)
		self.assertEqual(result.original_case, source.name)

	def test_ip_billing_items_use_configured_non_zero_rates(self):
		fake_db = Mock()
		fake_db.get_value.side_effect = [100, 250]

		with patch.object(frappe.local, "db", fake_db, create=True):
			items = get_configured_billing_items(IP_BILLING_STAGES["Filing"])

		self.assertEqual([item[2] for item in items], [100, 250])

	def test_ip_billing_rejects_missing_or_zero_rates(self):
		fake_db = Mock()
		fake_db.get_value.side_effect = [0, None]

		with (
			patch.object(frappe.local, "db", fake_db, create=True),
			patch.object(
				ip_case_module.frappe,
				"throw",
				side_effect=frappe.ValidationError("missing rates"),
			),
		):
			with self.assertRaises(frappe.ValidationError):
				get_configured_billing_items(IP_BILLING_STAGES["Filing"])

	def test_status_change_is_added_before_save(self):
		case = Mock()
		case.case_status = "Filed"
		case.flags = frappe._dict()
		case.has_value_changed.return_value = True
		with (
			patch.object(ip_case_module, "nowdate", return_value="2026-08-08"),
			patch.object(frappe.local, "session", frappe._dict(user="ip@example.com"), create=True),
		):
			IPCase.before_save(case)

		case.append.assert_called_once_with(
			"status_history",
			{"status": "Filed", "date_of_change": "2026-08-08", "changed_by": "ip@example.com"},
		)

	def test_ip_case_currency_defaults_to_usd(self):
		ip_case = frappe._dict(currency=None)

		IPCase.validate(ip_case)

		self.assertEqual(ip_case.currency, DEFAULT_CURRENCY)

	def test_ip_case_keeps_selected_currency(self):
		ip_case = frappe._dict(currency="ETB")

		IPCase.validate(ip_case)

		self.assertEqual(ip_case.currency, "ETB")

	def test_ip_case_currency_ignores_old_invalid_currency_values(self):
		self.assertEqual(get_case_currency(frappe._dict(currency="0.000000000")), DEFAULT_CURRENCY)

	def test_ip_case_autoname_uses_tbest_prefix_and_case_type_code(self):
		ip_case = frappe._dict(case_type="Trademark Renewal")

		with patch(
			"ip_management.ip_management.doctype.ip_case.ip_case.make_autoname",
			return_value="TBeST/RW/26/00001",
		) as make_name:
			IPCase.autoname(ip_case)

		make_name.assert_called_once_with("TBeST/RW/.YY./.#####")
		self.assertEqual(ip_case.name, "TBeST/RW/26/00001")
