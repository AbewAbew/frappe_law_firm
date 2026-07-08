import unittest
from unittest.mock import patch

import frappe

from ip_management.ip_management.doctype.ip_case.ip_case import DEFAULT_CURRENCY, IPCase, get_case_currency


class TestIPCaseCurrency(unittest.TestCase):
	def test_ip_case_currency_defaults_to_usd(self):
		ip_case = frappe._dict(currency=None)

		IPCase.validate(ip_case)

		self.assertEqual(ip_case.currency, DEFAULT_CURRENCY)

	def test_ip_case_keeps_selected_currency(self):
		ip_case = frappe._dict(currency="ETB")

		IPCase.validate(ip_case)

		self.assertEqual(ip_case.currency, "ETB")

	def test_ip_case_currency_ignores_old_invalid_currency_values(self):
		self.assertEqual(get_case_currency(frappe._dict(currency="0.000000000")), DEFAULT_CURRENCY)

	def test_ip_case_autoname_uses_tbest_prefix_and_case_type_code(self):
		ip_case = frappe._dict(case_type="Trademark Renewal")

		with patch(
			"ip_management.ip_management.doctype.ip_case.ip_case.make_autoname",
			return_value="TBeST/RW/26/00001",
		) as make_name:
			IPCase.autoname(ip_case)

		make_name.assert_called_once_with("TBeST/RW/.YY./.#####")
		self.assertEqual(ip_case.name, "TBeST/RW/26/00001")
