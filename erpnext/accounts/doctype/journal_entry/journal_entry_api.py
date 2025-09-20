import base64
import frappe
import json

# Authentication helper
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
	if (
		not user
		or frappe.utils.password.get_decrypted_password("User", user.name, "api_secret") != api_secret
	):
		frappe.local.response["http_status_code"] = 401
		return None

	return user

import frappe
from frappe import _

# --- Utility for auth check (adjust to your needs) ---
def authenticate_user():
    # Example check: only logged-in users
    if frappe.session.user == "Guest":
        return False
    return True


# ✅ Create Journal Entry
@frappe.whitelist(allow_guest=False)
def create_journal_entry():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.new_doc("Journal Entry")
        doc.update(data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Journal Entry created successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Journal Entry API")
        return {"error": str(e)}


# ✅ Get all Journal Entries
@frappe.whitelist(allow_guest=False)
def get_all_journal_entries():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        docs = frappe.get_all("Journal Entry", fields=["name","from_template","company", "posting_date", "voucher_type", "total_debit", "total_credit"])
        return docs
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Journal Entries API")
        return {"error": str(e)}


# ✅ Get Journal Entry by ID
@frappe.whitelist(allow_guest=False)
def get_journal_entry(docname):
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        doc = frappe.get_doc("Journal Entry", docname)
        return doc.as_dict()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Journal Entry by ID API")
        return {"error": str(e)}


# ✅ Update Journal Entry
@frappe.whitelist(allow_guest=False)
def update_journal_entry(docname):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.get_doc("Journal Entry", docname)
        doc.update(data)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Journal Entry updated successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Journal Entry API")
        return {"error": str(e)}


# ✅ Delete Journal Entry
@frappe.whitelist(allow_guest=False)
def delete_journal_entry(docname):
    if frappe.request.method != "DELETE":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only DELETE method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        frappe.delete_doc("Journal Entry", docname, ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Journal Entry deleted successfully", "name": docname}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Journal Entry API")
        return {"error": str(e)}

# ✅ Create Journal Entry Template
@frappe.whitelist(allow_guest=False)
def create_journal_entry_template():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.new_doc("Journal Entry Template")
        doc.update(data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Journal Entry Template created successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Journal Entry Template API")
        return {"error": str(e)}


# ✅ Get all Journal Entry Templates
@frappe.whitelist(allow_guest=False)
def get_all_journal_entry_templates():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        docs = frappe.get_all("Journal Entry Template", fields=["name", "template_title", "voucher_type"])
        return docs
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Journal Entry Templates API")
        return {"error": str(e)}


# ✅ Get Journal Entry Template by ID
@frappe.whitelist(allow_guest=False)
def get_journal_entry_template(docname):
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        doc = frappe.get_doc("Journal Entry Template", docname)
        return doc.as_dict()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Journal Entry Template by ID API")
        return {"error": str(e)}


# ✅ Update Journal Entry Template
@frappe.whitelist(allow_guest=False)
def update_journal_entry_template(docname):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        doc = frappe.get_doc("Journal Entry Template", docname)
        doc.update(data)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Journal Entry Template updated successfully", "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Journal Entry Template API")
        return {"error": str(e)}


# ✅ Delete Journal Entry Template
@frappe.whitelist(allow_guest=False)
def delete_journal_entry_template(docname):
    if frappe.request.method != "DELETE":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only DELETE method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        frappe.delete_doc("Journal Entry Template", docname, ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Journal Entry Template deleted successfully", "name": docname}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Journal Entry Template API")
        return {"error": str(e)}
