import frappe
import json
import base64
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt
from frappe.utils import today

# ------------------ AUTH ------------------
def authenticate_user():
    auth = frappe.get_request_header("Authorization")
    if not auth or not auth.startswith("Basic "):
        frappe.local.response["http_status_code"] = 401
        return None
    try:
        decoded = base64.b64decode(auth.split("Basic ")[1]).decode()
        api_key, api_secret = decoded.split(":")
        user = frappe.db.get("User", {"api_key": api_key})
        if not user:
            raise
        real = get_decrypted_password("User", user.name, "api_secret")
        if real != api_secret:
            raise
        return user
    except:
        frappe.local.response["http_status_code"] = 401
        return None
    
# -----------------------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def createPurchaseReceipt():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.new_doc("Purchase Receipt")
        doc.update(data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Purchase Receipt created successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Receipt API")
        return {"error": str(e)}
    

# ✅ GET all Purchase Receipts
@frappe.whitelist(allow_guest=False)
def get_all_purchase_receipts():
    """Fetch all Purchase Receipts"""
    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        receipts = frappe.get_all(
            "Purchase Receipt",
            fields=[
                "name",
                "supplier",
                "posting_date",
                "status",
                "company",
                "total",
                "total_taxes_and_charges",
                "grand_total",
                "rounded_total",
                "in_words",
                "currency",
                "docstatus"
            ],
            order_by="creation desc"
        )

        return {
            "status": "success",
            "count": len(receipts),
            "data": receipts
        }

    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Receipt API Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ✅ GET Purchase Receipt by ID
@frappe.whitelist(allow_guest=False)
def get_purchase_receipt_by_id(name=None):
    """Fetch Purchase Receipt by name (ID)"""
    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    if not name:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing required parameter: name"}

    try:
        doc = frappe.get_doc("Purchase Receipt", name)
        data = doc.as_dict()

        return {
            "status": "success",
            "data": data
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Purchase Receipt {name} not found"}
    except Exception as e:
        frappe.log_error(message=str(e), title="Purchase Receipt Get By ID API Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}