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

# ------------------  Purchase taxes charges api ------------------

@frappe.whitelist(allow_guest=True)
def list_pur_tax_char_temp():
    return get_list_api("Purchase Taxes and Charges Template")



# ------------------ CREATE ------------------
@frappe.whitelist(allow_guest=True)
def create_pur_tax_char_temp():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        data = json.loads(frappe.request.data or "{}")
        doc = frappe.get_doc({
            "doctype": "Purchase Taxes and Charges Template",
            **data
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Purchase Taxes Template")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ------------------ DETAILS ------------------
@frappe.whitelist(allow_guest=True)
def details_pur_tax_char_temp(name):
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        doc = frappe.get_doc("Purchase Taxes and Charges Template", name)
        return {"data": doc.as_dict()}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Details Purchase Taxes Template")
        frappe.local.response["http_status_code"] = 404
        return {"error": str(e)}


# ------------------ UNIVERSAL DETAILS ------------------
@frappe.whitelist(allow_guest=True)
def details_pur_tax_char_temp_api():
    if frappe.request.method != "POST":  # use POST since body is required
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    try:
        # Read JSON body
        data = json.loads(frappe.request.data or "{}")
        name = data.get("name")  # expecting { "name": "CGST - MDD" }

        if not name:
            frappe.local.response["http_status_code"] = 400
            return {"error": "Missing parameter: name"}

        # Fetch the document
        doc = frappe.get_doc("Purchase Taxes and Charges Template", name)
        return {"success": True, "data": doc.as_dict()}

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"success": False, "error": f"Record '{name}' not found"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Details API for Purchase Taxes Template")
        frappe.local.response["http_status_code"] = 500
        return {"success": False, "error": str(e)}




@frappe.whitelist(allow_guest=True)
def update_pur_tax_char_temp_api():
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT method allowed"}

    if not authenticate_user():
        frappe.local.response["http_status_code"] = 401
        return {"error": "Unauthorized"}

    try:
     
        data = json.loads(frappe.request.get_data(as_text=True) or "{}")
        name = data.get("name")  # expecting: { "name": "CGST - MDD", "title": "New Title", ... }

        if not name:
            frappe.local.response["http_status_code"] = 400
            return {"error": "Missing parameter: name"}

        doc = frappe.get_doc("Purchase Taxes and Charges Template", name)

        update_data = {k: v for k, v in data.items() if k != "name"}
        if not update_data:
            return {"error": "No fields provided to update"}

        doc.update(update_data)
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "message": f"Record '{name}' updated successfully", "data": doc.as_dict()}

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"success": False, "error": f"Record '{name}' not found"}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Purchase Taxes Template")
        frappe.local.response["http_status_code"] = 500
        return {"success": False, "error": str(e)}
