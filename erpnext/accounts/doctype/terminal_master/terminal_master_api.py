import base64
import json
import frappe
from frappe.utils.password import get_decrypted_password
from pymysql.err import IntegrityError

# ------------------ AUTH ------------------
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


# ------------------ GENERIC LIST ------------------
def get_list_api(doctype):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}
 
    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}
 
    try:
        limit_start = int(frappe.form_dict.get("limit_start", 0))
        raw_limit = frappe.form_dict.get("limit_page_length", 10)
 
        total = frappe.db.count(doctype)
        if str(raw_limit).lower() in ("0", "all"):
            limit_page_length = total
        else:
            try:
                limit_page_length = int(raw_limit)
            except ValueError:
                limit_page_length = 10
 
        MAX_LIMIT = 1000
        if limit_page_length > MAX_LIMIT:
            limit_page_length = MAX_LIMIT
 
        data = frappe.get_all(
            doctype,
            fields=["*"],
            order_by="creation desc",
            limit_start=limit_start,
            limit_page_length=limit_page_length,
        )
 
        return {
            "total": total,
            "limit_start": limit_start,
            "applied_limit": limit_page_length,
            "returned_count": len(data),
            "data": data,
        }
 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"List API for {doctype}")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ------------------ MODE OF PAYMENT APIs ------------------

@frappe.whitelist(allow_guest=True)
def list_terminal_master():
    return get_list_api("Terminal Master")
