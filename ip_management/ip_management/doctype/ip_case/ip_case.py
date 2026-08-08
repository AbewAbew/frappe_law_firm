# Copyright (c) 2025, Law Firm and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.model.naming import make_autoname
from frappe.utils import add_days, add_months, flt, getdate, now_datetime, nowdate
from law_management.law_management.doctype.legal_bill.legal_bill import (
	build_billing_source_key,
	ensure_billing_source_is_available,
	set_billing_source,
)

DEFAULT_CURRENCY = "USD"
SUPPORTED_CASE_CURRENCIES = {"USD", "ETB"}
IP_INVOICE_CREATOR_ROLES = {"IP Manager", "System Manager"}
IP_MASTER_UPDATE_ROLES = {"IP Manager", "System Manager"}
IP_BILLING_STAGES = {
	"Filing": {
		"items": (
			("Trademark Filing Fee", "Official fee for trademark filing."),
			("Professional Fee - Filing", "Professional fee for filing services."),
		),
		"attachment_field": "proof_of_filing",
	},
	"Publication": {
		"items": (
			("Trademark Publication Fee", "Official fee for trademark publication."),
			("Professional Fee - Publication", "Professional fee for publication services."),
		),
		"attachment_field": "advertisement_document",
	},
	"Renewal Publication": {
		"items": (
			("Trademark Renewal Publication Fee", "Official fee for renewal publication."),
			("Professional Fee - Renewal Publication", "Professional fee for renewal services."),
		),
		"attachment_field": "advertisement_document",
	},
	"Registration": {
		"items": (
			("Trademark Registration Fee", "Official fee for trademark registration."),
			("Professional Fee - Registration", "Professional fee for registration services."),
		),
		"attachment_field": "certificate_document",
	},
	"Recordal Filing": {
		"items": (
			("Recordal Filing Fee", "Official fee for recordal filing."),
			("Professional Fee - Recordal Filing", "Professional fee for recordal filing."),
		),
		"attachment_field": "proof_of_filing_recordal",
	},
	"Recordal Publication": {
		"items": (
			("Recordal Publication Fee", "Official fee for recordal publication."),
			("Professional Fee - Recordal Publication", "Professional fee for recordal publication."),
		),
		"attachment_field": "advertisement_copy",
	},
}


def get_case_currency(doc):
	currency = doc.get("currency") if hasattr(doc, "get") else getattr(doc, "currency", None)
	if currency in SUPPORTED_CASE_CURRENCIES:
		return currency

	return DEFAULT_CURRENCY


def can_create_ip_invoice(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(IP_INVOICE_CREATOR_ROLES.intersection(frappe.get_roles(user)))


def check_ip_invoice_creation_permission(user=None):
	if not can_create_ip_invoice(user):
		frappe.throw(
			"Only an IP Manager or System Manager can create an IP invoice.",
			frappe.PermissionError,
		)


def check_ip_master_update_permission(user=None):
	user = user or frappe.session.user
	if user != "Administrator" and not IP_MASTER_UPDATE_ROLES.intersection(frappe.get_roles(user)):
		frappe.throw(
			"Only an IP Manager or System Manager can apply an approved Recordal to the Master IP Case.",
			frappe.PermissionError,
		)


def _require_recordal_values(recordal, required_fields):
	missing = [label for fieldname, label in required_fields if not recordal.get(fieldname)]
	if missing:
		frappe.throw("Complete these Recordal fields before updating the Master: " + ", ".join(missing))


def _record_master_change(master_doc, recordal, field_changed, old_value, new_value, timestamp):
	master_doc.append(
		"master_change_history",
		{
			"recordal_case": recordal.name,
			"recordal_type": recordal.recordal_type,
			"field_changed": field_changed,
			"old_value": str(old_value or ""),
			"new_value": str(new_value or ""),
			"changed_on": timestamp,
			"changed_by": frappe.session.user,
		},
	)


def _apply_recordal_to_master(recordal, master_doc, timestamp):
	recordal_type = recordal.recordal_type
	changes = []

	if recordal_type == "Assignment (Transfer)":
		_require_recordal_values(recordal, (("new_owner", "New Owner"),))
		old_owner = master_doc.trademark_owner
		if old_owner == recordal.new_owner:
			frappe.throw("The Master IP Case already has the selected New Owner.")
		master_doc.trademark_owner = recordal.new_owner
		changes.append(("Trademark Owner", old_owner, recordal.new_owner))

	elif recordal_type == "License Agreement":
		_require_recordal_values(
			recordal,
			(
				("licensee", "Licensee"),
				("license_type", "License Type"),
				("license_effective_date", "Effective Date"),
				("license_agreement_doc", "License Agreement"),
			),
		)
		if recordal.license_expiry_date and getdate(recordal.license_expiry_date) < getdate(
			recordal.license_effective_date
		):
			frappe.throw("License Expiry Date cannot be before the Effective Date.")
		if any(
			row.source_recordal == recordal.name for row in (master_doc.get("registered_licenses") or [])
		):
			frappe.throw("This License Agreement is already registered on the Master IP Case.")

		master_doc.append(
			"registered_licenses",
			{
				"licensee": recordal.licensee,
				"license_type": recordal.license_type,
				"effective_date": recordal.license_effective_date,
				"expiry_date": recordal.license_expiry_date,
				"quality_control": recordal.quality_control,
				"agreement_document": recordal.license_agreement_doc,
				"source_recordal": recordal.name,
				"recorded_on": timestamp,
				"recorded_by": frappe.session.user,
			},
		)
		license_summary = f"{recordal.license_type} license to {recordal.licensee}"
		changes.append(("Registered License", "", license_summary))

	elif recordal_type == "Change of Name":
		_require_recordal_values(recordal, (("new_value", "New Value"),))
		old_name = master_doc.trademark_name
		if old_name == recordal.new_value:
			frappe.throw("The Master IP Case already has the supplied Trademark Name.")
		master_doc.trademark_name = recordal.new_value
		changes.append(("Trademark Name", old_name, recordal.new_value))

	elif recordal_type == "Change of Address":
		_require_recordal_values(recordal, (("new_value", "New Value"),))
		if not master_doc.trademark_owner:
			frappe.throw("The Master IP Case has no Trademark Owner whose address can be updated.")
		owner_doc = frappe.get_doc("Trademark Owner", master_doc.trademark_owner)
		old_address = owner_doc.full_address
		if old_address == recordal.new_value:
			frappe.throw("The Trademark Owner already has the supplied address.")
		owner_doc.full_address = recordal.new_value
		owner_doc.save(ignore_permissions=True)
		master_doc.owner_address = recordal.new_value
		changes.append(("Trademark Owner Address", old_address, recordal.new_value))

	elif recordal_type == "Merger":
		_require_recordal_values(
			recordal,
			(
				("merger_successor_owner", "Successor Owner"),
				("merger_effective_date", "Merger Effective Date"),
				("merger_document", "Merger Document"),
			),
		)
		old_owner = master_doc.trademark_owner
		if old_owner == recordal.merger_successor_owner:
			frappe.throw("The Master IP Case already has the selected Successor Owner.")
		master_doc.trademark_owner = recordal.merger_successor_owner
		changes.append(("Trademark Owner (Merger)", old_owner, recordal.merger_successor_owner))

	else:
		frappe.throw(f"Recordal Type {recordal_type or '(blank)'} cannot update a Master IP Case.")

	for field_changed, old_value, new_value in changes:
		_record_master_change(
			master_doc,
			recordal,
			field_changed,
			old_value,
			new_value,
			timestamp,
		)

	return changes


def set_case_deadlines(doc):
	doc.priority_document_deadline = (
		add_days(doc.application_date, 90)
		if doc.priority_claimed and doc.application_date
		else None
	)

	if doc.case_type == "New Trademark" and doc.advertisement_date:
		doc.opposition_period_end = add_days(doc.advertisement_date, 60)

	if doc.case_type == "New Trademark":
		registration_basis = doc.opposition_deadline_extended or doc.opposition_period_end
		if registration_basis:
			doc.registration_fee_due_date = add_days(registration_basis, 1)

	doc.registration_fee_deadline = (
		add_days(doc.registration_fee_due_date, 90) if doc.registration_fee_due_date else None
	)
	doc.non_use_cancellation_date = (
		add_months(doc.certificate_issued_date, 36) if doc.certificate_issued_date else None
	)

	if doc.case_type == "Trademark Renewal":
		doc.renewal_date_display = add_months(doc.renewal_due_date, 84) if doc.renewal_due_date else None
	else:
		doc.renewal_date_display = add_months(doc.application_date, 84) if doc.application_date else None

	doc.current_expiration_date = (
		add_months(doc.original_application_date, 84) if doc.original_application_date else None
	)
	doc.next_renewal_date = (
		add_months(doc.current_expiration_date, 84) if doc.current_expiration_date else None
	)

	if doc.case_type == "Trademark Renewal" and doc.renewal_filed_date and doc.renewal_due_date:
		filed_date = getdate(doc.renewal_filed_date)
		if filed_date <= getdate(add_months(doc.renewal_due_date, 3)):
			doc.late_renewal_status = "Regular Renewal"
		elif filed_date <= getdate(add_months(doc.renewal_due_date, 9)):
			doc.late_renewal_status = "Late Renewal (Penalty Applies)"
		else:
			doc.late_renewal_status = "Cancelled / Time Barred"
	else:
		doc.late_renewal_status = None

	for office_action in doc.office_actions or []:
		if office_action.office_action_date and not office_action.response_deadline:
			office_action.response_deadline = add_days(office_action.office_action_date, 90)


def get_derived_case_status(doc, current_date=None):
	if doc.case_type == "Recordals":
		if doc.publication_date:
			return "Published"
		if doc.decision_outcome == "Approved" or doc.recordal_registration_date:
			return "Registered"
		if doc.filing_date:
			return "Filed"
		return "New"

	if doc.case_type == "Trademark Renewal":
		if doc.advertisement_published:
			return "Renewed"
		if doc.application_date:
			return "Renewal Filed"
		return "New"

	if doc.case_type != "New Trademark":
		return doc.case_status

	if doc.registration_number and doc.certificate_issued_date:
		return "Registered"
	if doc.registration_fee_due_date and getdate(doc.registration_fee_due_date) <= getdate(
		current_date or nowdate()
	):
		return "Registration Fee Due"
	if doc.opposition_filed:
		return "Opposed"
	if doc.advertisement_published:
		return "Advertised"

	office_actions = doc.office_actions or []
	if any(action.response_date for action in office_actions):
		return "Response Filed"
	if office_actions:
		return "Office Action Received"
	if doc.application_date:
		return "Filed"
	return "New"


def get_configured_billing_items(stage):
	configured_items = []
	missing_rates = []

	for service_name, description in stage["items"]:
		standard_rate = flt(frappe.db.get_value("Legal Service Item", service_name, "standard_rate"))
		if standard_rate <= 0:
			missing_rates.append(service_name)
		configured_items.append((service_name, description, standard_rate))

	if missing_rates:
		frappe.throw(
			"Set a non-zero Standard Rate on these Legal Service Items before creating the invoice: "
			+ ", ".join(missing_rates)
		)

	return configured_items


@frappe.whitelist()
def make_renewal(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.case_type = "Trademark Renewal"
		target.case_origin = "Internal"
		target.source_origin = "Internal"
		target.linked_ip_case = source.name
		target.original_case = source.name
		target.amended_from = None
		target.currency = get_case_currency(source)

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
		# TBeST/{Code}/.YY./.#####

		# Map Case Type to Code
		type_map = {
			"New Trademark": "NR",
			"Trademark Renewal": "RW",
			"Recordals": "RC",
			"Disputes & Surrenders": "DS"
		}

		code = type_map.get(self.case_type, "NR") # Default to NR if unknown? Or IP? User specified 3 types. I'll default to 'NR' or 'IP' if new types appear.
		# User prompt implies explicit mapping.

		self.name = make_autoname(f"TBeST/{code}/.YY./.#####")

	def validate(self):
		self.currency = get_case_currency(self)
		set_case_deadlines(self)
		self.case_status = get_derived_case_status(self)

	def before_save(self):
		if self.has_value_changed("case_status"):
			self.append(
				"status_history",
				{
					"status": self.case_status,
					"date_of_change": nowdate(),
					"changed_by": frappe.session.user,
				},
			)

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

	@frappe.whitelist()
	def create_legal_bill(self, bill_type):
		"""
		Creates a Legal Bill for the Case
		bill_type: 'Filing', 'Publication', 'Registration', 'Renewal Publication'
		"""
		check_ip_invoice_creation_permission()

		if not self.applicant:
			frappe.throw("Please select a Trademark Owner (Applicant) first.")

		stage = IP_BILLING_STAGES.get(bill_type)
		if not stage:
			frappe.throw(f"Unsupported IP billing stage: {bill_type}.")

		frappe.db.sql("SELECT name FROM `tabIP Case` WHERE name = %s FOR UPDATE", (self.name,))
		source_key = build_billing_source_key("IP Stage", "IP Case", self.name, bill_type)
		ensure_billing_source_is_available(source_key)

		configured_items = get_configured_billing_items(stage)
		attachment_field = stage["attachment_field"]

		# Create Legal Bill
		lb = frappe.new_doc("Legal Bill")
		lb.customer = self.applicant
		lb.reference_doctype = "IP Case"
		lb.case_reference = self.name
		lb.bill_date = nowdate()
		lb.due_date = nowdate() # Can be adjusted
		lb.currency = get_case_currency(self)
		set_billing_source(lb, "IP Stage", "IP Case", self.name, bill_type)

		# Add Items
		for service_name, description, standard_rate in configured_items:
			row = lb.append("items", {})
			row.service = service_name
			row.description = description
			row.qty = 1
			row.rate = standard_rate
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
		check_ip_master_update_permission()

		if not self.linked_ip_case:
			frappe.throw("Linked IP Case is missing.")

		if (
			self.case_type != "Recordals"
			or self.source_origin != "Internal"
			or self.decision_outcome != "Approved"
		):
			frappe.throw("Case must be an Approved Recordal to update the Master Case.")
		if self.linked_ip_case == self.name:
			frappe.throw("A Recordal cannot update itself as the Master IP Case.")

		for case_name in sorted((self.name, self.linked_ip_case)):
			frappe.db.sql("SELECT name FROM `tabIP Case` WHERE name = %s FOR UPDATE", (case_name,))

		if frappe.db.get_value("IP Case", self.name, "master_update_applied"):
			frappe.throw("This approved Recordal has already been applied to its Master IP Case.")

		master_doc = frappe.get_doc("IP Case", self.linked_ip_case)
		if master_doc.case_type == "Recordals":
			frappe.throw("The linked Master IP Case cannot itself be a Recordal.")

		timestamp = now_datetime()
		changes = _apply_recordal_to_master(self, master_doc, timestamp)
		master_doc.save(ignore_permissions=True)

		summary = "; ".join(
			f"{field_changed}: {old_value or '(blank)'} -> {new_value or '(blank)'}"
			for field_changed, old_value, new_value in changes
		)
		frappe.db.set_value(
			"IP Case",
			self.name,
			{
				"master_update_applied": 1,
				"master_updated_on": timestamp,
				"master_updated_by": frappe.session.user,
				"master_update_summary": summary,
			},
		)
		self.master_update_applied = 1
		self.master_updated_on = timestamp
		self.master_updated_by = frappe.session.user
		self.master_update_summary = summary
		return f"Master IP Case {master_doc.name} updated. {summary}"

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_agents(doctype, txt, searchfield, start, page_len, filters):
	# Filter Users by Role 'IP Manager' OR 'IP Staff'
	# We join tabUser with tabHas Role
	return frappe.db.sql("""
		SELECT DISTINCT u.name, u.full_name
		FROM `tabUser` u
		JOIN `tabHas Role` hr ON hr.parent = u.name
		WHERE hr.role IN ('IP Manager', 'IP Staff')
		AND u.enabled = 1
		AND u.name LIKE %(txt)s
		ORDER BY u.full_name
		LIMIT %(start)s, %(page_len)s
	""", {
		'txt': f"%{txt}%",
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
