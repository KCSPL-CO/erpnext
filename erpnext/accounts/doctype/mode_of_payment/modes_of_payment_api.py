import frappe
import json
import base64
from frappe.utils.password import get_decrypted_password


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
        user = frappe.db.get("User", {"api_key": api_key})
        if not user:
            return None
        real_secret = get_decrypted_password("User", user.name, "api_secret")
        return user if real_secret == api_secret else None
    except Exception:
        return None


@frappe.whitelist(allow_guest=True)
def get_all_modes_of_payment():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        modes = frappe.get_all(
            "Mode of Payment",
            filters={"enabled": 1},  # Only active modes
            fields=["*"],
            order_by="name asc"
        )

        # Fields to exclude
        EXCLUDE_FIELDS = {
            "amended_from", "_user_tags", "_comments", "_assign", "_liked_by",
            "_seen", "idx", "naming_series", "doctype", "owner", "docstatus",
            "modified_by", "creation", "modified", "parent", "parenttype", "parentfield"
        }

        cleaned_data = []
        for row in modes:
            filtered = {k: v for k, v in row.items() if k not in EXCLUDE_FIELDS}
            cleaned_data.append(filtered)

        return {
            "message": "Modes of Payment fetched successfully",
            "count": len(cleaned_data),
            "data": cleaned_data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_all_modes_of_payment API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
