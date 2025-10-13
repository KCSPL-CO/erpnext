import frappe
from frappe.utils import today
import json
import base64
from frappe.utils.password import get_decrypted_password
from frappe.utils import getdate, today



# --------------------------
# ✅ Authentication Method
# --------------------------
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
    if not user:
        frappe.local.response["http_status_code"] = 401
        return None

    real_secret = get_decrypted_password("User", user.name, "api_secret")
    if real_secret != api_secret:
        frappe.local.response["http_status_code"] = 401
        return None

    return user


# --------------------------
# ✅ Create incoterm (POST)
# --------------------------
@frappe.whitelist(allow_guest=True)
def create_incoterm():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed. Use POST."}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    data = json.loads(frappe.request.data)
    doc = frappe.new_doc("Incoterm")

    for key, value in data.items():
        doc.set(key, value)

    doc.insert()
    frappe.db.commit()

    return {"status": "success", "message": "incoterm created", "name": doc.name}


# --------------------------
# ✅ Get All incoterms (GET)
# --------------------------
@frappe.whitelist(allow_guest=True)
def get_all_incoterms():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed. Use GET."}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    incoterms = frappe.get_all("Incoterm", fields=["code","title","description","name"])
    return incoterms


# --------------------------
# ✅ Get incoterm by ID (GET)
# --------------------------
@frappe.whitelist(allow_guest=True)
def get_incoterm_by_id(name):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Method Not Allowed. Use GET."}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    if not frappe.db.exists("Incoterm", name):
        frappe.local.response["http_status_code"] = 404
        return {"error": "incoterm not found"}

    return frappe.get_doc("Incoterm", name)
