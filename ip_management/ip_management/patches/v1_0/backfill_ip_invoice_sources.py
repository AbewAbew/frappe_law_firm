import frappe
from law_management.law_management.doctype.legal_bill.legal_bill import build_billing_source_key

from ip_management.ip_management.doctype.ip_case.ip_case import IP_BILLING_STAGES

SERVICE_TO_STAGE = {
	service_name: stage_name
	for stage_name, stage in IP_BILLING_STAGES.items()
	for service_name, _description in stage["items"]
}


def _get_ip_billing_stage(items):
	stages = {SERVICE_TO_STAGE.get(item.get("service")) for item in items}
	stages.discard(None)
	return stages.pop() if len(stages) == 1 else None


def execute():
	bills = frappe.get_all(
		"Legal Bill",
		filters={
			"reference_doctype": "IP Case",
			"case_reference": ["is", "set"],
			"billing_source_key": ["is", "not set"],
		},
		fields=["name", "case_reference"],
		order_by="creation asc",
	)

	for bill in bills:
		items = frappe.get_all(
			"Legal Bill Item",
			filters={"parent": bill.name, "parenttype": "Legal Bill", "parentfield": "items"},
			fields=["service"],
		)
		stage = _get_ip_billing_stage(items)
		if not stage:
			continue

		frappe.db.set_value(
			"Legal Bill",
			bill.name,
			{
				"billing_source_type": "IP Stage",
				"billing_source_reference": stage,
				"billing_source_key": build_billing_source_key(
					"IP Stage",
					"IP Case",
					bill.case_reference,
					stage,
				),
			},
			update_modified=False,
		)
