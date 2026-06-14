import frappe


DEFAULT_CURRENCY = "USD"


def execute():
	if not frappe.db.table_exists("IP Case") or not frappe.db.has_column("IP Case", "currency"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabIP Case`
		SET currency = %s
		WHERE currency IS NULL
		OR currency = ''
		OR currency NOT IN (SELECT name FROM `tabCurrency`)
		""",
		DEFAULT_CURRENCY,
	)
