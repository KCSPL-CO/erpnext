import base64
import frappe
from frappe.utils.password import get_decrypted_password

# ------------------- Authentication ---------------------
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
        frappe.log_error(frappe.get_traceback(), "Auth Decode Error")
        frappe.local.response["http_status_code"] = 401
        return None

    user = frappe.db.get("User", {"api_key": api_key})
    if not user:
        frappe.local.response["http_status_code"] = 401
        return None

    real_secret = get_decrypted_password("User", user.name, "api_secret")
    if real_secret != api_secret:
        frappe.local.response["http_status_code"] = 401
        return None

    return user

# ------------------- CREATE ---------------------
# import frappe
# from frappe.utils.response import build_response

@frappe.whitelist(allow_guest=True)
def createSalesInvoice():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        data = frappe.request.get_json()

        # Check and get item_code or item
        first_item = data.get("items", [{}])[0]
        item_code = first_item.get("item_code") or first_item.get("item")
        naming_series = "ACC-SINV-.YYYY.-"  # default fallback series

        if item_code:
            item_group = frappe.db.get_value("Item", item_code, "item_group")
            year = frappe.utils.now_datetime().year

            series_map = {
                "Drug": f"DRUG-SINV-{year}-",
                "Laboratory": f"LAB-SINV-{year}-",
                "Services": f"SERV-SINV-{year}-",
                "Consumable": f"CONS-SINV-{year}-",
                "Raw Material": f"RAW-SINV-{year}-",
                "Products": f"PROD-SINV-{year}-",
                "Sub Assemblies": f"SUB-SINV-{year}-",
                "Demo Item Group": f"DEMO-SINV-{year}-",
            }

            if item_group in series_map:
                naming_series = series_map[item_group]

        # Now create Sales Invoice
        doc = frappe.new_doc("Sales Invoice")
        doc.naming_series = naming_series
        doc.update(data)

        # Optional: double-check naming_series didn't get overwritten
        if not doc.naming_series:
            doc.naming_series = naming_series

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Sales Invoice created successfully",
            "name": doc.name,
            "series_used": naming_series
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Invoice API")
        return {"error": str(e)}

# ------------------- GET ALL ---------------------
@frappe.whitelist(allow_guest=True)
def get_all_sales_invoices():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only GET allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = frappe.get_all("Sales Invoice", fields=["*", ])
        return {"message": "Fetched successfully", "success": True, "data": data}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Sales Invoices")
        return {"message": str(e), "success": False}

# ------------------- GET BY ID ---------------------
@frappe.whitelist(allow_guest=True)
def get_sales_invoice_by_id(name):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only GET allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        doc = frappe.get_doc("Sales Invoice", name)
        return {"message": "Fetched successfully", "success": True, "data": doc.as_dict()}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Invoice By ID")
        return {"message": str(e), "success": False}

# ------------------- UPDATE ---------------------
@frappe.whitelist(allow_guest=True)
def update_sales_invoice():
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only PUT allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = frappe.request.get_json()
        name = data.get("name")
        if not name:
            return {"message": "Missing Sales Invoice name", "success": False}

        doc = frappe.get_doc("Sales Invoice", name)
        doc.update(data)
        doc.save(ignore_permissions=True)

        # Submit the invoice if not already
        if doc.docstatus < 1:
            doc.submit()

        # Only proceed if the invoice is paid
        if doc.status == "Paid":
            items = data.get("items", [])
            for item in items:
                ref_name = item.get("reference_name")
                ref_type = item.get("reference_type")

                if ref_type and ref_name and frappe.db.exists(ref_type, ref_name):
                    updates = {}
                    meta = frappe.get_meta(ref_type)

                    if "invoiced" in [d.fieldname for d in meta.fields]:
                        updates["invoiced"] = 1

                    if "billing_status" in [d.fieldname for d in meta.fields]:
                        updates["billing_status"] = "Completed"

                    if updates:
                        frappe.db.set_value(ref_type, ref_name, updates)

        frappe.db.commit()

        return {
            "message": "Sales Invoice updated successfully",
            "success": True,
            "data": doc.as_dict()
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Sales Invoice")
        return {"message": str(e), "success": False}

