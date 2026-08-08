import frappe
from frappe.permissions import add_permission, update_permission_property

IP_CASE_REVIEW_PERMISSIONS = {
	"read": 1,
	"report": 1,
	"export": 1,
	"print": 1,
	"create": 0,
	"write": 0,
	"delete": 0,
	"submit": 0,
	"cancel": 0,
	"amend": 0,
	"share": 0,
	"email": 0,
	"import": 0,
}

IP_MANAGER_LEGAL_BILL_PERMISSIONS = {
	"read": 1,
	"create": 1,
	"write": 1,
	"report": 1,
	"export": 1,
	"print": 1,
	"email": 1,
	"delete": 0,
	"submit": 0,
	"cancel": 0,
	"amend": 0,
	"share": 0,
	"import": 0,
}


def execute():
	for role in ("Legal Finance", "HR Manager"):
		_apply_permissions_to_existing_overrides("IP Case", role, IP_CASE_REVIEW_PERMISSIONS)

	_apply_permissions_to_existing_overrides(
		"Legal Bill",
		"IP Manager",
		IP_MANAGER_LEGAL_BILL_PERMISSIONS,
	)


def _apply_permissions_to_existing_overrides(doctype, role, permissions):
	# Sites without Role Permission Manager overrides use the DocPerm shipped with the apps.
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
		frappe.clear_cache(doctype=doctype)
		return

	filters = {
		"parent": doctype,
		"role": role,
		"permlevel": 0,
		"if_owner": 0,
	}
	if not frappe.db.exists("Custom DocPerm", filters):
		add_permission(doctype, role, permlevel=0, ptype="read")

	for permission_type, value in permissions.items():
		update_permission_property(
			doctype,
			role,
			0,
			permission_type,
			value,
			validate=False,
		)

	frappe.clear_cache(doctype=doctype)
