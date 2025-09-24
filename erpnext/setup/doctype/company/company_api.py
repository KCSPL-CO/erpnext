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

# ------------------- GET ALL ---------------------
@frappe.whitelist(allow_guest=True)
def get_all_company():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only GET allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    try:
        data = frappe.get_all("Company", fields=["name","company_name","default_currency","country","date_of_establishment","parent_company","company_logo" ])
        return {"message": "Fetched successfully", "success": True, "data": data}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All New Company")
        return {"message": str(e), "success": False}