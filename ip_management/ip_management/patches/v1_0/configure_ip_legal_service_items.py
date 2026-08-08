import frappe

from ip_management.ip_management.doctype.ip_case.ip_case import IP_BILLING_STAGES


def execute():
	for stage in IP_BILLING_STAGES.values():
		for service_name, description in stage["items"]:
			if frappe.db.exists("Legal Service Item", service_name):
				continue

			service = frappe.new_doc("Legal Service Item")
			service.service_name = service_name
			service.standard_description = description
			service.standard_rate = 0
			service.insert(ignore_permissions=True)
