import frappe
import json
from frappe import _
from erpnext.controllers.accounts_controller import update_child_qty_rate
from frappe.utils import cstr
import base64
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt


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
	if not user or get_decrypted_password("User", user.name, "api_secret") != api_secret:
		frappe.local.response["http_status_code"] = 401
		return None

	return user


@frappe.whitelist()
def indent_api():
    if frappe.request.method != "POST":
        frappe.throw(_("Only POST method allowed"))

    # ✅ Authenticate
    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()

    sales_order_name = data.get("name")
    items = data.get("items", [])

    if not sales_order_name or not items:
        frappe.throw(_("Missing 'name' or 'items' in request"))

    trans_items = []

    for item in items:
        item_code = item.get("item_code")
        if not item_code:
            continue

        qty = item.get("qty", 1)
        item_name = item.get("item_name") or item_code
        description = item.get("description") or item_code
        reference_dt = item.get("reference_dt", "")
        reference_dn = item.get("reference_dn", "")

        # Fetch item rate
        rate = get_item_rate(item_code)
        if rate is None:
            frappe.throw(f"Rate not found for item: {item_code}")

        trans_items.append({
            "item_code": item_code,
            "item_name": item_name,
            "description": description,
            "qty": qty,
            "rate": rate,
            "reference_dt": reference_dt,
            "reference_dn": reference_dn
        })

    # Structure to return and also pass to update_child_qty_rate
    response_data = {
        "parent_doctype": "Sales Order",
        "parent_doctype_name": sales_order_name,
        "child_docname": "items",
        "trans_items": trans_items
    }

    # Now call update_child_qty_rate
    result = update_child_qty_rate(
        parent_doctype=response_data["parent_doctype"],
        trans_items=json.dumps(response_data["trans_items"]),  # ✅ convert to JSON string
        parent_doctype_name=response_data["parent_doctype_name"],
        child_docname="items"
    )


    return {
        "message":"Item Indented Sucessfully" ,
        "sucess":True,
        "update_result": response_data
    }

def get_item_rate(item_code):
    """Fetch item rate from Item Price or fallback to Item.standard_rate"""
    rate = frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, "price_list_rate")
    if rate:
        return float(rate)

    item = frappe.get_doc("Item", item_code)
    return float(item.standard_rate) if item.standard_rate else None
