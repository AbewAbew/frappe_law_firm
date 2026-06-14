import unittest

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
