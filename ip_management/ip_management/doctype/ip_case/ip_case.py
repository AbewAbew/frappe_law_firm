# Copyright (c) 2025, Law Firm and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days, getdate
from frappe.model.mapper import get_mapped_doc
from frappe.model.naming import make_autoname

@frappe.whitelist()
def make_renewal(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.case_type = "Trademark Renewal"
		target.case_origin = "Internal"
		target.original_case = source.name
		target.amended_from = None

		# Clear Status / Workflow fields
		target.case_status = "New"
		target.certificate_issued_date = None
		target.registration_number = None # New Reg No might be different or same, but usually cleared until issued
		target.registration_fee_due_date = None
		target.registration_fee_deadline = None
		target.box_number = None

		# Map specific valid details that shouldn't change
		target.trademark_name = source.trademark_name
		target.trademark_owner = source.trademark_owner
		target.classes = source.classes
		target.goods_description = source.goods_description

		# Pre-fill Original Registration Number if available
		if source.registration_number:
			target.original_registration_number = source.registration_number

	doclist = get_mapped_doc("IP Case", source_name, {
		"IP Case": {
			"doctype": "IP Case",
			"field_map": {
				"trademark_name": "trademark_name",
				"trademark_owner": "trademark_owner",
				"applicant": "applicant",
				"local_agent": "local_agent"
			}
		}
	}, target_doc, set_missing_values)

	return doclist

class IPCase(Document):
	def autoname(self):
		# TbesT/{Code}/.YY./.#####

		# Map Case Type to Code
		type_map = {
			"New Trademark": "NR",
			"Trademark Renewal": "RW",
			"Recordals": "RC",
			"Disputes & Surrenders": "DS"
		}

		code = type_map.get(self.case_type, "NR") # Default to NR if unknown? Or IP? User specified 3 types. I'll default to 'NR' or 'IP' if new types appear.
		# User prompt implies explicit mapping.

		self.name = make_autoname(f"Mla/{code}/.YY./.#####")

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

	def _get_or_create_item(self, item_code, item_name, default_income_account):
		if not frappe.db.exists("Item", item_code):
			item = frappe.new_doc("Item")
			item.item_code = item_code
			item.item_name = item_name
			item.item_group = "Services"
			item.is_stock_item = 0
			item.include_item_in_manufacturing = 0
			# Set defaults for sales
			item.is_sales_item = 1
			item.income_account = default_income_account
			item.insert(ignore_permissions=True)
		return item_code

	def _get_or_create_legal_service_item(self, service_name, description=""):
		if not frappe.db.exists("Legal Service Item", service_name):
			lsi = frappe.new_doc("Legal Service Item")
			lsi.service_name = service_name
			lsi.standard_description = description
			lsi.standard_rate = 0 # Default to 0, will be updated in bill if needed
			lsi.insert(ignore_permissions=True)
		return service_name

	@frappe.whitelist()
	def create_legal_bill(self, bill_type):
		"""
		Creates a Legal Bill for the Case
		bill_type: 'Filing', 'Publication', 'Registration', 'Renewal Publication'
		"""
		if not self.applicant:
			frappe.throw("Please select a Trademark Owner (Applicant) first.")

		# Define Services for each stage
		items_to_add = []
		attachment_field = None
		bill_remarks = f"Bill for IP Case: {self.trademark_name} - {bill_type} Stage"

		if bill_type == "Filing":
			items_to_add = [
				{"name": "Trademark Filing Fee", "desc": "Official fee for trademark filing."},
				{"name": "Professional Fee - Filing", "desc": "Professional fee for filing services."}
			]
			attachment_field = "proof_of_filing"

		elif bill_type == "Publication":
			items_to_add = [
				{"name": "Trademark Publication Fee", "desc": "Official fee for trademark publication."},
				{"name": "Professional Fee - Publication", "desc": "Professional fee for publication services."}
			]
			attachment_field = "advertisement_document"

		elif bill_type == "Renewal Publication":
			items_to_add = [
				{"name": "Trademark Renewal Publication Fee", "desc": "Official fee for renewal publication."},
				{"name": "Professional Fee - Renewal Publication", "desc": "Professional fee for renewal services."}
			]
			# Reuse advertisement doc if same field used for renewal
			# In logic, renewal ad usually is same field?
			# Checking ip_case.js: create_renewal_publication_invoice -> "Renewal Publication"
			attachment_field = "advertisement_document"

		elif bill_type == "Registration":
			items_to_add = [
				{"name": "Trademark Registration Fee", "desc": "Official fee for trademark registration."},
				{"name": "Professional Fee - Registration", "desc": "Professional fee for registration services."}
			]
			attachment_field = "certificate_document"

		elif bill_type == "Recordal Filing":
			items_to_add = [
				{"name": "Recordal Filing Fee", "desc": "Official fee for recordal filing."},
				{"name": "Professional Fee - Recordal Filing", "desc": "Professional fee for recordal filing."}
			]
			attachment_field = "proof_of_filing_recordal"

		elif bill_type == "Recordal Publication":
			items_to_add = [
				{"name": "Recordal Publication Fee", "desc": "Official fee for recordal publication."},
				{"name": "Professional Fee - Recordal Publication", "desc": "Professional fee for recordal publication."}
			]
			attachment_field = "advertisement_copy"

		# Create Legal Bill
		lb = frappe.new_doc("Legal Bill")
		lb.customer = self.applicant
		lb.reference_doctype = "IP Case"
		lb.case_reference = self.name
		lb.bill_date = nowdate()
		lb.due_date = nowdate() # Can be adjusted
		lb.currency = "ETB" # Default, or fetch from customer/settings

		# Add Items
		for item_data in items_to_add:
			service_name = self._get_or_create_legal_service_item(item_data["name"], item_data["desc"])

			row = lb.append("items", {})
			row.service = service_name
			row.description = item_data["desc"]
			row.qty = 1
			row.rate = 0 # Fetch from Service Item standard rate if set? Or keep 0 for user input.
			row.amount = row.qty * row.rate


		lb.insert()

		# --- Attachment Logic ---
		# Link the file to the Legal Bill
		# Legal Bill has `invoice_file` (Attach) for the MAIN bill file usually, but we can also stick the proof there?
		# Or generic attachment.
		# User Request: "New legal bill(fees) doctype... attach this attachement docuents to the new legal bill we create too."
		# I will attach to `invoice_file` if empty, or just add as attachment.

		if attachment_field:
			file_url = self.get(attachment_field)
			if file_url:
				# 1. Set as 'invoice_file' if it serves as the supporting doc?
				# Maybe not, invoice_file is usually the generated invoice PDF.
				# I will create a File attachment linked to the Legal Bill.

				file_doc = frappe.new_doc("File")
				file_doc.file_url = file_url
				file_doc.file_name = file_url.split("/")[-1]
				file_doc.attached_to_doctype = "Legal Bill"
				file_doc.attached_to_name = lb.name
				file_doc.save(ignore_permissions=True)

				# Optional: If Legal Bill has a dedicated field for "Supporting Doc", map it.
				# But for now, standard attachment.

		return lb.name

	@frappe.whitelist()
	def create_invoice(self, invoice_type):
		"""
		Deprecated: Use create_legal_bill
		"""
		return self.create_legal_bill(invoice_type)

	@frappe.whitelist()
	def update_master_case(self):
		"""
		Updates the Master IP Case based on the Recordal outcome.
		Triggered by Button in IP Case (Recordal).
		"""
		if not self.linked_ip_case:
			frappe.throw("Linked IP Case is missing.")

		if self.case_type != "Recordals" or self.decision_outcome != "Approved":
			frappe.throw("Case must be an Approved Recordal to update the Master Case.")

		master_doc = frappe.get_doc("IP Case", self.linked_ip_case)
		msg = ""

		if self.recordal_type == "Assignment (Transfer)":
			if self.new_owner:
				old_owner = master_doc.trademark_owner
				master_doc.trademark_owner = self.new_owner
				# Recalculate/Refetch address logic if auto-fetch exists on save
				master_doc.save(ignore_permissions=True)
				msg = f"Master Case {master_doc.name} updated. Owner changed from {old_owner} to {self.new_owner}."

		elif self.recordal_type == "Change of Name":
			if self.new_value:
				master_doc.trademark_name = self.new_value
				master_doc.save(ignore_permissions=True)
				msg = f"Master Case {master_doc.name} updated. Trademark Name changed."

		elif self.recordal_type == "Change of Address":
			if self.new_value:
				master_doc.owner_address = self.new_value
				master_doc.save(ignore_permissions=True)
				msg = f"Master Case {master_doc.name} updated. Owner Address updated."

		if msg:
			return msg
		else:
			return "No updates applied to Master Case (Check Recordal Type logic)."

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_agents(doctype, txt, searchfield, start, page_len, filters):
	# Filter Users by Role 'IP Manager' OR 'IP Staff'
	# We join tabUser with tabHas Role
	return frappe.db.sql(f"""
		SELECT DISTINCT u.name, u.full_name
		FROM `tabUser` u
		JOIN `tabHas Role` hr ON hr.parent = u.name
		WHERE hr.role IN ('IP Manager', 'IP Staff')
		AND u.enabled = 1
		AND u.name LIKE %(txt)s
		ORDER BY u.full_name
		LIMIT %(start)s, %(page_len)s
	""", {
		'txt': "%%%s%%" % txt,
		'start': start,
		'page_len': page_len
	})

def daily_deadline_check():
	# Deadlines to check and their labels
	# (Field Name, Friendly Name)
	deadlines_to_check = [
		("priority_document_deadline", "Priority Document Deadline"),
		("registration_fee_deadline", "Registration Fee Deadline"),
		("non_use_cancellation_date", "Non-Use Vulnerability Date"),
		("renewal_date_display", "Renewal Date"),
		("opposition_period_end", "Opposition Period End"),
		("opposition_deadline_extended", "Extended Opposition Deadline")
	]

	# Get all active cases
	# We exclude Cancelled. We might exclude Registered for some, but Renewal applies to Registered.
	cases = frappe.get_all("IP Case", filters={"case_status": ["!=", "Cancelled"]}, fields=["name", "trademark_name", "local_agent_email"] + [d[0] for d in deadlines_to_check])

	today = frappe.utils.getdate(nowdate())

	for case in cases:
		if not case.local_agent_email:
			continue

		# Check standard fields
		for field, label in deadlines_to_check:
			date_val = case.get(field)
			if date_val:
				match_deadline(case, label, date_val, today)

		# Check Office Actions (Child Table)
		oas = frappe.get_all("IP Office Action", filters={"parent": case.name}, fields=["office_action_date", "response_deadline", "response_date"])
		for oa in oas:
			if oa.response_deadline and not oa.response_date:
				match_deadline(case, f"Office Action Response ({oa.office_action_date})", oa.response_deadline, today)

def match_deadline(case, label, target_date, today):
	# Ensure target_date is date obj
	target_date = frappe.utils.getdate(target_date)
	diff = (target_date - today).days

	msg = None
	if diff == 7:
		msg = f"Upcoming Deadline (1 Week): {label}"
	elif diff == 1:
		msg = f"Urgent Deadline (Tomorrow): {label}"
	elif diff == 0:
		msg = f"Deadline Today: {label}"

	if msg:
		send_deadline_email(case, msg, label, target_date)

def send_deadline_email(case, subject, label, date):
	frappe.sendmail(
		recipients=[case.local_agent_email],
		subject=f"{subject} - {case.trademark_name} ({case.name})",
		message=f"""
			<h3>Deadline Alert</h3>
			<p><b>Case:</b> {case.trademark_name} ({case.name})</p>
			<p><b>Deadline:</b> {label}</p>
			<p><b>Date:</b> {date}</p>
			<p>Please take necessary action.</p>
		"""
	)
