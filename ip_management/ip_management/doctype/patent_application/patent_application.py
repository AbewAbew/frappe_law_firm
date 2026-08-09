# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import add_months, now_datetime

APPLICATION_TYPE_CODES = {
	"Patent of Invention": "P",
	"Patent of Introduction": "P",
	"Utility Model": "UM",
	"Industrial Design": "ID",
}
PATENT_TRANSITION_ROLES = {"IP Manager", "System Manager"}
PATENT_STATUS_TRANSITIONS = {
	"Draft": ("Filed", "Withdrawn"),
	"Filed": ("Formal Exam", "Refused", "Withdrawn"),
	"Formal Exam": ("Substantive Exam", "Refused", "Withdrawn"),
	"Substantive Exam": ("Published", "Refused", "Withdrawn"),
	"Published": ("Granted", "Refused", "Withdrawn"),
	"Granted": ("Surrendered", "Expired"),
	"Refused": (),
	"Withdrawn": (),
	"Surrendered": (),
	"Expired": (),
}
PATENT_STATUS_REQUIREMENTS = {
	"Formal Exam": (("formal_exam_date", "Formal Exam Date"),),
	"Substantive Exam": (("substantive_exam_date", "Substantive Exam Date"),),
	"Published": (("publication_date", "Publication Date"),),
	"Granted": (("grant_date", "Grant Date"),),
	"Expired": (("expiration_date", "Expiration Date"),),
}


def get_patent_naming_series(application_type):
	code = APPLICATION_TYPE_CODES.get(application_type)
	if not code:
		frappe.throw("Select a valid Application Type before saving the patent application.")

	return f"ET/{code}/.YY./.#####"


def get_allowed_patent_transitions(status):
	return PATENT_STATUS_TRANSITIONS.get(status, ())


def can_transition_patent_status(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(PATENT_TRANSITION_ROLES.intersection(frappe.get_roles(user)))


class PatentApplication(Document):
	def autoname(self):
		self.naming_series = get_patent_naming_series(self.application_type)
		self.name = make_autoname(self.naming_series)

	def before_save(self):
		self.calculate_deadlines()

	def validate(self):
		self.validate_status_change()
		if self.status == "Filed":
			self.validate_checklist()

	def validate_status_change(self):
		if self.is_new():
			if self.status not in (None, "", "Draft"):
				frappe.throw("A new Patent Application must start in Draft status.")
			self.status = "Draft"
			return

		if self.has_value_changed("status") and not self.flags.get("authorized_status_transition"):
			frappe.throw("Use the Change Status action to update Patent Application status.")

	@frappe.whitelist()
	def transition_status(self, new_status):
		if not can_transition_patent_status():
			frappe.throw(
				"Only an IP Manager or System Manager can change Patent Application status.",
				frappe.PermissionError,
			)
		if self.is_new():
			frappe.throw("Save the Patent Application before changing its status.")

		frappe.db.sql(
			"SELECT name FROM `tabPatent Application` WHERE name = %s FOR UPDATE",
			(self.name,),
		)
		current_status = frappe.db.get_value("Patent Application", self.name, "status") or "Draft"
		if self.status != current_status:
			self.reload()

		allowed_transitions = get_allowed_patent_transitions(current_status)
		if new_status not in allowed_transitions:
			frappe.throw(f"Patent Application cannot move from {current_status} to {new_status}.")

		self.validate_transition_requirements(new_status)
		self.status = new_status
		self.flags.authorized_status_transition = True
		self.append(
			"status_history",
			{
				"status": new_status,
				"changed_on": now_datetime(),
				"changed_by": frappe.session.user,
			},
		)
		self.save()
		return self.status

	def validate_transition_requirements(self, new_status):
		if new_status == "Filed":
			self.validate_checklist()

		missing_fields = [
			label for fieldname, label in PATENT_STATUS_REQUIREMENTS.get(new_status, ()) if not self.get(fieldname)
		]
		if missing_fields:
			frappe.throw(f"Set {', '.join(missing_fields)} before changing status to {new_status}.")

	def validate_checklist(self):
		# Document Checklist Validation
		if not self.description_file:
			frappe.throw("Description File is required before changing status to Filed.")
		if not self.claims_file:
			frappe.throw("Claims File is required before changing status to Filed.")
		if self.agent_lawyer and not self.power_of_attorney:
			frappe.throw("Power of Attorney is required when an Agent is selected.")
		# Assignment evidence requirements remain deferred pending the firm's IP counsel decision.

	def calculate_deadlines(self):
		if self.filing_date:
			# Priority Deadline: 12 months from filing
			self.priority_deadline = add_months(self.filing_date, 12)

			# Annuity Start Date: 1 year after filing
			if not self.annuity_start_date:
				self.annuity_start_date = add_months(self.filing_date, 12)
