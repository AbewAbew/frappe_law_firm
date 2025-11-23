# Copyright (c) 2025, Law Firm and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days

class IPCase(Document):
	def on_update(self):
		if self.has_value_changed("case_status"):
			# 1. Log to History
			self.append("status_history", {
				"status": self.case_status,
				"date_of_change": nowdate(),
				"changed_by": frappe.session.user
			})
			
			# 2. Find Matching Rule
			rule = frappe.db.get_value("IP Workflow Rule", {
				"triggering_status": self.case_status,
				"request_type_filter": ["in", [self.request_type, None]],
				"is_active": 1
			}, ["name", "days_to_deadline", "task_template"], as_dict=True)
			
			if rule:
				# 3. Calculate Deadline
				deadline = add_days(nowdate(), rule.days_to_deadline)
				self.next_notification_date = deadline
				
				# 4. Create Task
				self.create_ip_task(rule, deadline)

	def create_ip_task(self, rule, deadline):
		task_desc = frappe.render_template(rule.task_template, self.as_dict())
		new_task = frappe.get_doc({
			"doctype": "IP Task",
			"subject": task_desc,
			"ip_case": self.name,
			"due_date": deadline,
			"status": "Open",
			"generated_by_rule": rule.name,
			"assigned_to": frappe.session.user # Assign to current user by default
		})
		new_task.insert(ignore_permissions=True)
