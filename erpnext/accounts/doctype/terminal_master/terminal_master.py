# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class TerminalMaster(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		bank: DF.Link | None
		company: DF.Link | None
		disable: DF.Check
		naming_series: DF.Literal["TRM-.QR.-", "TRM-.EDC.-"]
		terminal: DF.Data | None
		terminal_type: DF.Literal["QR code", "EDC"]
		vendor: DF.Link | None
	# end: auto-generated types
	pass


# ✅ Auto-generate terminal ID based on Type
# def autoname(doc, method):
# 	prefix = "TRM"

# 	if doc.terminal_type:
# 		if "QR" in doc.terminal_type.upper():
# 			type_code = "QR"
# 		elif "ECD" in doc.terminal_type.upper():
# 			type_code = "ECD"
# 		else:
# 			type_code = "GEN"
# 	else:
# 		type_code = "GEN"

	# Generate something like TRM-ECD-001 or TRM-QR-002
	# doc.naming_series = make_autoname(f"{prefix}-.{type_code}.-.###")
	# doc.naming_series = doc.naming_series
