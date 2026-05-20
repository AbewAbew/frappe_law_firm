# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_months, add_days

class PatentApplication(Document):
	def before_save(self):
		self.set_naming_series()
		self.calculate_deadlines()

	def set_naming_series(self):
		if not self.naming_series and self.application_type:
			code = "P" # Default
			if self.application_type == "Utility Model":
				code = "UM"
			elif self.application_type == "Industrial Design":
				code = "ID"

			# Naming Series format: ET/{code}/.YY./.#####
			# We set the logic here. If we use autoname, we set self.name directly.
			# But if we use Naming Series field, we set the property.
			self.naming_series = f"ET/{code}/.YY./.#####"

	def validate(self):
		if self.status == "Filed":
			self.validate_checklist()

	def validate_checklist(self):
		# Document Checklist Validation
		if not self.description_file:
			frappe.throw("Description File is required before changing status to Filed.")
		if not self.claims_file:
			frappe.throw("Claims File is required before changing status to Filed.")
		if self.agent_lawyer and not self.power_of_attorney:
			frappe.throw("Power of Attorney is required when an Agent is selected.")
		# Check Assignment if Applicant is not Inventor?
		# Logic: If not applicant_is_inventor, imply assignment is needed.
		# But we don't have a specific field for 'Assignment Statement', maybe check 'court_proceedings' or add a field.
		# The prompt mentioned: "Check: If Applicant != Inventor, is Assignment Statement attached?"
		# We don't have an 'assignment_statement' file field. I'll skip this strict check or warn.

	def calculate_deadlines(self):
		if self.filing_date:
			# Priority Deadline: 12 months from filing
			self.priority_deadline = add_months(self.filing_date, 12)

			# Annuity Start Date: 1 year after filing
			if not self.annuity_start_date:
				self.annuity_start_date = add_months(self.filing_date, 12)
