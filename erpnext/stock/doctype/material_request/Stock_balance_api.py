# file: your_app/your_module/api/stock_api.py

import frappe
from frappe import _

@frappe.whitelist(allow_guest=False)
def get_items_by_warehouse(warehouse, from_date=None, to_date=None):
    """
    Returns a list of items in a specific warehouse similar to Stock Balance report.
    """
    if not warehouse:
        frappe.throw(_("Warehouse is required"))

    stock_items = frappe.db.sql("""
        SELECT
            bin.item_code,
            item.item_name,
            bin.warehouse,
            bin.actual_qty,
            bin.valuation_rate,
            bin.stock_value
        FROM
            `tabBin` bin
        LEFT JOIN
            `tabItem` item ON bin.item_code = item.name
        WHERE
            bin.warehouse = %s AND bin.actual_qty > 0
        ORDER BY
            bin.item_code
    """, (warehouse,), as_dict=True)

    return {
        "status": "success",
        "data": stock_items
    }
