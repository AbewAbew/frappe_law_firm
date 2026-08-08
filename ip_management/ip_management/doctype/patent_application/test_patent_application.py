# Copyright (c) 2025, Law Firm and Contributors
# See license.txt

import unittest
from unittest.mock import patch

import frappe

from ip_management.ip_management.doctype.patent_application import patent_application
from ip_management.ip_management.doctype.patent_application.patent_application import (
	PatentApplication,
	can_transition_patent_status,
	get_allowed_patent_transitions,
	get_patent_naming_series,
)


class TestPatentApplication(unittest.TestCase):
	def test_provisional_status_sequence(self):
		self.assertEqual(get_allowed_patent_transitions("Draft"), ("Filed", "Withdrawn"))
		self.assertEqual(
			get_allowed_patent_transitions("Substantive Exam"),
			("Published", "Refused", "Withdrawn"),
		)
		self.assertEqual(get_allowed_patent_transitions("Granted"), ("Surrendered", "Expired"))
		self.assertEqual(get_allowed_patent_transitions("Expired"), ())

	def test_only_ip_manager_and_system_manager_can_transition_status(self):
		with patch.object(patent_application.frappe, "get_roles", return_value=["IP Manager"]):
			self.assertTrue(can_transition_patent_status("manager@example.com"))
		with patch.object(patent_application.frappe, "get_roles", return_value=["IP Staff"]):
			self.assertFalse(can_transition_patent_status("staff@example.com"))

	def test_direct_status_change_is_rejected(self):
		doc = unittest.mock.Mock()
		doc.is_new.return_value = False
		doc.has_value_changed.return_value = True
		doc.flags = frappe._dict()

		with patch.object(
			patent_application.frappe,
			"throw",
			side_effect=frappe.ValidationError("use action"),
		):
			with self.assertRaises(frappe.ValidationError):
				PatentApplication.validate_status_change(doc)

	def test_authorized_transition_updates_status_and_history(self):
		doc = unittest.mock.Mock()
		doc.name = "ET/P/26/00001"
		doc.status = "Draft"
		doc.flags = frappe._dict()
		doc.is_new.return_value = False
		fake_db = unittest.mock.Mock()
		fake_db.get_value.return_value = "Draft"
		changed_on = "2026-08-08 12:00:00"

		with (
			patch.object(frappe.local, "db", fake_db, create=True),
			patch.object(patent_application, "can_transition_patent_status", return_value=True),
			patch.object(patent_application, "now_datetime", return_value=changed_on),
			patch.object(
				frappe.local,
				"session",
				frappe._dict(user="manager@example.com"),
				create=True,
			),
		):
			result = PatentApplication.transition_status(doc, "Filed")

		self.assertEqual(result, "Filed")
		self.assertTrue(doc.flags.authorized_status_transition)
		doc.append.assert_called_once_with(
			"status_history",
			{
				"status": "Filed",
				"changed_on": changed_on,
				"changed_by": "manager@example.com",
			},
		)
		doc.save.assert_called_once_with()

	def test_application_types_use_the_existing_series_codes(self):
		self.assertEqual(get_patent_naming_series("Patent of Invention"), "ET/P/.YY./.#####")
		self.assertEqual(get_patent_naming_series("Patent of Introduction"), "ET/P/.YY./.#####")
		self.assertEqual(get_patent_naming_series("Utility Model"), "ET/UM/.YY./.#####")
		self.assertEqual(get_patent_naming_series("Industrial Design"), "ET/ID/.YY./.#####")

	def test_autoname_sets_series_before_generating_name(self):
		doc = frappe._dict(application_type="Utility Model", naming_series=None, name=None)

		with patch.object(patent_application, "make_autoname", return_value="ET/UM/26/00001") as naming:
			PatentApplication.autoname(doc)

		naming.assert_called_once_with("ET/UM/.YY./.#####")
		self.assertEqual(doc.naming_series, "ET/UM/.YY./.#####")
		self.assertEqual(doc.name, "ET/UM/26/00001")
