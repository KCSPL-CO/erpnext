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


@frappe.whitelist(allow_guest=True)
def list_terminal_master():
    return get_list_api("Terminal Master")

# ------------------ TERMINAL MASTER APIs ------------------

@frappe.whitelist(allow_guest=True)
def create_terminal_master():
    """Create a new Terminal Master record"""
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method is allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    try:
        # Handle both raw bytes and parsed JSON
        if isinstance(frappe.request.data, (bytes, bytearray)):
            data = json.loads(frappe.request.data.decode("utf-8"))
        else:
            data = frappe.form_dict or {}

        terminal_type = data.get("terminal_type")

        # Naming series mapping
        series_map = {
            "QR code": "TRM-.QR.-",
            "ECD": "TRM-.ECD.-"
        }

        naming_series = series_map.get(terminal_type, "TRM-")

        # Create document
        doc = frappe.get_doc({
            "doctype": "Terminal Master",
            "naming_series": naming_series,
            "terminal_type": terminal_type,
            "disable": data.get("disable"),
            "bank": data.get("bank"),
            "terminal": data.get("terminal"),
            "company": data.get("company"),
            "vendor": data.get("vendor")
        })

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Terminal Master created successfully", "name": doc.name}

    except IntegrityError as e:
        frappe.db.rollback()
        return {"error": "Database integrity error: " + str(e)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Terminal Master API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_terminal_master_details():
    """Fetch details of a specific Terminal Master by ID (passed in body)"""
    if frappe.request.method not in ["GET", "POST"]:
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET or POST methods allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    try:
        # Handle both raw bytes and parsed JSON
        if isinstance(frappe.request.data, (bytes, bytearray)):
            data = json.loads(frappe.request.data.decode("utf-8"))
        else:
            data = frappe.form_dict or {}

        terminal_id = data.get("id") or data.get("name")

        if not terminal_id:
            frappe.local.response["http_status_code"] = 400
            return {"error": "Missing 'id' in request body"}

        # Fetch the record
        doc = frappe.get_doc("Terminal Master", terminal_id)

        return {"message": "Success", "data": doc.as_dict()}

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Terminal Master with ID '{terminal_id}' not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Terminal Master Details API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def update_terminal_master():
    """Update an existing Terminal Master record"""
    if frappe.request.method not in ["POST", "PUT"]:
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST or PUT methods allowed"}

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    try:
        # Parse incoming data safely (bytes or dict)
        if isinstance(frappe.request.data, (bytes, bytearray)):
            data = json.loads(frappe.request.data.decode("utf-8"))
        else:
            data = frappe.form_dict or {}

        terminal_id = data.get("id") or data.get("name")
        if not terminal_id:
            frappe.local.response["http_status_code"] = 400
            return {"error": "Missing 'id' in request body"}

        # Fetch document
        doc = frappe.get_doc("Terminal Master", terminal_id)

        # Update fields
        allowed_fields = ["terminal_type", "disable", "bank", "terminal", "company", "vendor"]
        for field in allowed_fields:
            if field in data:
                doc.set(field, data[field])

        # Automatically update naming_series based on terminal_type
        if "terminal_type" in data:
            if data["terminal_type"] == "QR code":
                doc.naming_series = "TRM-.QR.-"
            elif data["terminal_type"] == "ECD":
                doc.naming_series = "TRM-.ECD.-"

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Terminal Master updated successfully", "data": doc.as_dict()}

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": f"Terminal Master with ID '{terminal_id}' not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Terminal Master API")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}
