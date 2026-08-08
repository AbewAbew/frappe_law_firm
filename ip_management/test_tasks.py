import unittest
from unittest.mock import Mock, patch

import frappe

from ip_management import tasks


class TestIPTasks(unittest.TestCase):
	def test_renewal_deadline_query_uses_applicant_field(self):
		case = frappe._dict(
			name="TBeST/RW/26/00001",
			application_number="APP-001",
			trademark_name="Test Mark",
			renewal_due_date="2026-10-01",
			applicant="CUST-001",
			firm_email="client@example.com",
		)
		fake_db = Mock()
		fake_db.sql.return_value = [case]

		with (
			patch.object(frappe.local, "db", fake_db, create=True),
			patch.object(tasks, "nowdate", return_value="2026-08-01"),
			patch.object(tasks, "add_days", return_value="2026-10-30"),
			patch.object(tasks, "date_diff", return_value=61),
			patch.object(tasks, "create_reminder_task") as create_task,
		):
			tasks.check_renewal_deadlines()

		query = fake_db.sql.call_args.args[0]
		self.assertIn("applicant", query)
		self.assertNotIn("firm_name", query)
		self.assertIn("CUST-001", create_task.call_args.kwargs["description"])


if __name__ == "__main__":
	unittest.main()
