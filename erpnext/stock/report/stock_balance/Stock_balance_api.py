import frappe
from frappe import _
from frappe.utils import nowdate
import base64

 
 # Authentication helper
def authenticate_user():
	auth_header = frappe.get_request_header("Authorization")
	if not auth_header or not auth_header.startswith("Basic "):
		frappe.local.response["http_status_code"] = 401
		return None

	try:
		encoded_token = auth_header.split("Basic ")[1]
		decoded = base64.b64decode(encoded_token).decode("utf-8")
		api_key, api_secret = decoded.split(":")
	except Exception:
		frappe.local.response["http_status_code"] = 401
		return None

	user = frappe.db.get("User", {"api_key": api_key})
	if (
		not user
		or frappe.utils.password.get_decrypted_password("User", user.name, "api_secret") != api_secret
	):
		frappe.local.response["http_status_code"] = 401
		return None

	return user

@frappe.whitelist(allow_guest=False)
def get_items_by_warehouse():
    """
    Returns item-wise stock summary for a warehouse using Stock Ledger Entry,
    including safety stock and end_of_life from Item master.
    """
 
    data = frappe.request.get_json()
    if not data:
        frappe.throw(_("Missing JSON payload"))
 
    warehouse = data.get("warehouse")
    from_date = data.get("from_date") or "2000-01-01"
    to_date = data.get("to_date") or nowdate()
 
    if not warehouse:
        frappe.throw(_("Warehouse is required"))
 
    stock_data = frappe.db.sql("""
        SELECT
            sle.item_code,
            i.item_name,
            i.safety_stock,
            i.end_of_life,
            sle.warehouse,
            SUM(sle.actual_qty) AS balance_qty,
            SUM(sle.stock_value_difference) AS stock_value
        FROM
            `tabStock Ledger Entry` sle
        LEFT JOIN
            `tabItem` i ON sle.item_code = i.name
        WHERE
            sle.warehouse = %s
            AND sle.posting_date BETWEEN %s AND %s
        GROUP BY
            sle.item_code, sle.warehouse
        HAVING
            balance_qty > 0
        ORDER BY
            sle.item_code
    """, (warehouse, from_date, to_date), as_dict=True)
 
    for row in stock_data:
        row["total_stock_qty"] = row["balance_qty"]
        row["total_stock_value"] = row["stock_value"]
 
    return {
        "status": "success",
        "data": stock_data
    }
 
