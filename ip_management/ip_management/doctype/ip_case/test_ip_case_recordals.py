import unittest
from datetime import datetime
from unittest.mock import Mock, call, patch

import frappe

from ip_management.ip_management.doctype.ip_case import ip_case
from ip_management.ip_management.doctype.ip_case.ip_case import (
	IPCase,
	_apply_recordal_to_master,
	check_ip_master_update_permission,
)


class FakeMaster:
	def __init__(self, **values):
		self.name = values.pop("name", "TBeST/NR/26/00001")
		self.case_type = values.pop("case_type", "New Trademark")
		self.trademark_owner = values.pop("trademark_owner", "Original Owner")
		self.trademark_name = values.pop("trademark_name", "ORIGINAL MARK")
		self.owner_address = values.pop("owner_address", "Old address")
		self.registered_licenses = values.pop("registered_licenses", [])
		self.master_change_history = values.pop("master_change_history", [])
		self.saved = False
		for key, value in values.items():
			setattr(self, key, value)

	def get(self, fieldname):
		return getattr(self, fieldname, None)

	def append(self, fieldname, values):
		row = frappe._dict(values)
		getattr(self, fieldname).append(row)
		return row

	def save(self, **kwargs):
		self.saved = True


def _recordal(recordal_type, **values):
	return frappe._dict(
		name="TBeST/RC/26/00001",
		recordal_type=recordal_type,
		**values,
	)


class TestIPCaseRecordalUpdates(unittest.TestCase):
	def setUp(self):
		self.timestamp = datetime(2026, 8, 8, 10, 30)

	def test_license_adds_registered_license_without_changing_owner(self):
		master = FakeMaster()
		recordal = _recordal(
			"License Agreement",
			licensee="Licensed Customer",
			license_type="Exclusive",
			license_effective_date="2026-08-01",
			license_expiry_date="2028-07-31",
			quality_control=1,
			license_agreement_doc="/private/files/license.pdf",
		)

		changes = _apply_recordal_to_master(recordal, master, self.timestamp)

		self.assertEqual(master.trademark_owner, "Original Owner")
		self.assertEqual(len(master.registered_licenses), 1)
		license_row = master.registered_licenses[0]
		self.assertEqual(license_row.licensee, "Licensed Customer")
		self.assertEqual(license_row.source_recordal, recordal.name)
		self.assertEqual(license_row.agreement_document, recordal.license_agreement_doc)
		self.assertEqual(changes, [("Registered License", "", "Exclusive license to Licensed Customer")])
		self.assertEqual(master.master_change_history[0].old_value, "")

	def test_license_requires_core_details_and_document(self):
		master = FakeMaster()
		recordal = _recordal(
			"License Agreement",
			licensee="Licensed Customer",
			license_type="Exclusive",
			license_effective_date="2026-08-01",
		)

		with self.assertRaises(frappe.ValidationError):
			_apply_recordal_to_master(recordal, master, self.timestamp)

	def test_license_rejects_expiry_before_effective_date(self):
		master = FakeMaster()
		recordal = _recordal(
			"License Agreement",
			licensee="Licensed Customer",
			license_type="Non-Exclusive",
			license_effective_date="2026-08-01",
			license_expiry_date="2026-07-31",
			license_agreement_doc="/private/files/license.pdf",
		)

		with self.assertRaises(frappe.ValidationError):
			_apply_recordal_to_master(recordal, master, self.timestamp)

	def test_license_rejects_duplicate_source_recordal(self):
		master = FakeMaster(
			registered_licenses=[frappe._dict(source_recordal="TBeST/RC/26/00001")]
		)
		recordal = _recordal(
			"License Agreement",
			licensee="Licensed Customer",
			license_type="Exclusive",
			license_effective_date="2026-08-01",
			license_agreement_doc="/private/files/license.pdf",
		)

		with self.assertRaises(frappe.ValidationError):
			_apply_recordal_to_master(recordal, master, self.timestamp)

	def test_merger_changes_owner_and_records_old_and_new_values(self):
		master = FakeMaster(trademark_owner="Merged Company")
		recordal = _recordal(
			"Merger",
			merger_successor_owner="Successor Company",
			merger_effective_date="2026-07-01",
			merger_document="/private/files/merger.pdf",
		)

		changes = _apply_recordal_to_master(recordal, master, self.timestamp)

		self.assertEqual(master.trademark_owner, "Successor Company")
		self.assertEqual(
			changes,
			[("Trademark Owner (Merger)", "Merged Company", "Successor Company")],
		)
		history = master.master_change_history[0]
		self.assertEqual(history.old_value, "Merged Company")
		self.assertEqual(history.new_value, "Successor Company")
		self.assertEqual(history.recordal_case, recordal.name)

	def test_merger_requires_successor_date_and_document(self):
		master = FakeMaster()
		recordal = _recordal("Merger", merger_successor_owner="Successor Company")

		with self.assertRaises(frappe.ValidationError):
			_apply_recordal_to_master(recordal, master, self.timestamp)

	def test_unsupported_recordal_type_throws_instead_of_reporting_success(self):
		with self.assertRaises(frappe.ValidationError):
			_apply_recordal_to_master(
				_recordal("Unsupported Type"), FakeMaster(), self.timestamp
			)

	def test_ip_staff_cannot_apply_master_update(self):
		with patch.object(ip_case.frappe, "get_roles", return_value=["IP Staff"]):
			with self.assertRaises(frappe.PermissionError):
				check_ip_master_update_permission("staff@tbestlaw.com")

	def test_ip_manager_can_apply_master_update(self):
		with patch.object(ip_case.frappe, "get_roles", return_value=["IP Manager"]):
			check_ip_master_update_permission("manager@tbestlaw.com")

	def test_update_master_locks_both_cases_and_sets_one_time_audit(self):
		recordal = _recordal(
			"Merger",
			linked_ip_case="TBeST/NR/26/00001",
			case_type="Recordals",
			source_origin="Internal",
			decision_outcome="Approved",
		)
		master = FakeMaster(name=recordal.linked_ip_case)
		changes = [("Trademark Owner (Merger)", "Old", "New")]

		with (
			patch.object(ip_case, "check_ip_master_update_permission"),
			patch.object(ip_case.frappe.db, "sql") as sql,
			patch.object(ip_case.frappe.db, "get_value", return_value=0),
			patch.object(ip_case.frappe, "get_doc", return_value=master),
			patch.object(ip_case, "_apply_recordal_to_master", return_value=changes),
			patch.object(ip_case, "now_datetime", return_value=self.timestamp),
			patch.object(ip_case.frappe.db, "set_value") as set_value,
		):
			message = IPCase.update_master_case(recordal)

		self.assertTrue(master.saved)
		self.assertEqual(sql.call_count, 2)
		self.assertEqual(
			sql.call_args_list,
			[
				call(
					"SELECT name FROM `tabIP Case` WHERE name = %s FOR UPDATE",
					("TBeST/NR/26/00001",),
				),
				call(
					"SELECT name FROM `tabIP Case` WHERE name = %s FOR UPDATE",
					("TBeST/RC/26/00001",),
				),
			],
		)
		set_value.assert_called_once()
		audit = set_value.call_args.args[2]
		self.assertEqual(audit["master_update_applied"], 1)
		self.assertIn("Trademark Owner (Merger)", audit["master_update_summary"])
		self.assertIn(master.name, message)

	def test_update_master_rejects_already_applied_recordal(self):
		recordal = _recordal(
			"Merger",
			linked_ip_case="TBeST/NR/26/00001",
			case_type="Recordals",
			source_origin="Internal",
			decision_outcome="Approved",
		)
		with (
			patch.object(ip_case, "check_ip_master_update_permission"),
			patch.object(ip_case.frappe.db, "sql"),
			patch.object(ip_case.frappe.db, "get_value", return_value=1),
			patch.object(ip_case.frappe, "get_doc") as get_doc,
		):
			with self.assertRaises(frappe.ValidationError):
				IPCase.update_master_case(recordal)

		get_doc.assert_not_called()


if __name__ == "__main__":
	unittest.main()
