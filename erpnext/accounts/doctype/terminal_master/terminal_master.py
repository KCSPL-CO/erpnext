# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class TerminalMaster(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company: DF.Link | None
		disable: DF.Check
		terminal: DF.Data | None
		terminal_id: DF.Data | None
		terminal_type: DF.Literal["Mobile UPI", "QR code", "Wallet"]
	# end: auto-generated types
	pass
