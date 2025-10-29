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
        raw_limit = frappe.form_dict.get("limit_page_length", 10000)
 
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
def list_mode_of_payments():
    return get_list_api("Mode of Payment")


# ---- Get Details ----
@frappe.whitelist(allow_guest=True)
def get_details_mode_of_payment():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    name = frappe.form_dict.get("name")
    if not name:
        frappe.local.response["http_status_code"] = 400
        return {"error": "Missing 'name' parameter"}

    try:
        doc = frappe.get_doc("Mode of Payment", name)
        return {"data": doc.as_dict()}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Mode of Payment '{name}' not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Mode of Payment Detail Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ---- Create ----
@frappe.whitelist(allow_guest=True)
def create_mode_of_payment():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    try:
        data = json.loads(frappe.request.data)

        doc = frappe.new_doc("Mode of Payment")
        doc.mode_of_payment = data.get("mode_of_payment")
        doc.type = data.get("type")
        doc.enabled = data.get("enabled", 1)

        # Example: Child table name (you can replace with your real one)
        # e.g. "Accounts" child table inside Mode of Payment
        if "accounts" in data:
            for row in data["accounts"]:
                doc.append("accounts", {
                    "company": row.get("company"),
                    "default_account": row.get("default_account")
                })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Created successfully", "name": doc.name}

    except IntegrityError as e:
        frappe.local.response["http_status_code"] = 409
        return {"error": "Duplicate entry", "details": str(e)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Mode of Payment Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ---- Update ----
@frappe.whitelist(allow_guest=True)
def update_mode_of_payment():
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    try:
        data = json.loads(frappe.request.data)
        name = data.get("name")
        if not name:
            frappe.local.response["http_status_code"] = 400
            return {"error": "Missing 'name' field"}

        doc = frappe.get_doc("Mode of Payment", name)

        # --- Allowed types for validation ---
        allowed_types = ["Cash", "Bank", "General", "Phone"]

        # Update main fields safely
        if "mode_of_payment" in data:
            doc.mode_of_payment = data["mode_of_payment"]

        if "enabled" in data:
            doc.enabled = int(data["enabled"])

        if "type" in data:
            new_type = data["type"]
            if new_type not in allowed_types:
                frappe.local.response["http_status_code"] = 400
                return {
                    "error": f"Invalid 'type'. Must be one of {allowed_types}"
                }
            doc.type = new_type

        # --- Update child table (accounts) ---
        if "accounts" in data:
            # Clear old child rows
            doc.set("accounts", [])
            for row in data["accounts"]:
                doc.append("accounts", {
                    "company": row.get("company"),
                    "default_account": row.get("default_account")
                })

        # Save and commit changes
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Mode of Payment updated successfully",
            "data": doc.as_dict()
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Mode of Payment '{name}' not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Mode of Payment Error")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def list_accounts():
    return get_list_api("Account")