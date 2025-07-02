import base64
import frappe
import json
from frappe.utils import cint
from frappe import _

# ------------------------------------
# 🔐 User Authentication
# ------------------------------------
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


@frappe.whitelist(allow_guest=False)
def list_material_requests():
    try:
        # Get parent Material Requests list without child fields
        requests = frappe.get_all("Material Request",
            fields=["name", "transaction_date", "schedule_date", "material_request_type", 
                    "set_from_warehouse","set_warehouse","status"],
            order_by="creation desc",
            limit_page_length=50
        )

        # For each parent doc, get child items
        for req in requests:
            doc = frappe.get_doc("Material Request", req["name"])
            # Get child table items as list of dicts
            req["items"] = []
            for item in doc.items:
                req["items"].append({
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "stock_qty": item.stock_qty,
                    "uom": item.uom,
                    "description": item.description,
                    
                })

        return {"status": "success", "data": requests}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Material Request API - List")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}





@frappe.whitelist(allow_guest=False)
def create_material_request():
    data = json.loads(frappe.local.form_dict.data)

    try:
        doc = frappe.new_doc("Material Request")
        doc.department = data.get("department")
        doc.requested_by = data.get("requested_by")
        doc.transaction_date = data.get("request_date")
        doc.purpose = data.get("purpose")
        doc.material_request_type = data.get("material_request_type", "Purchase")

        for item in data.get("items", []):
            doc.append("items", {
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "qty": item.get("qty"),
                "uom": item.get("uom"),
                "schedule_date": item.get("required_date"),
                "description": item.get("remarks")
            })

        doc.insert()
        frappe.db.commit()
        return {"status": "success", "message": "Material Request Created", "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Material Request API - Create")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}





@frappe.whitelist(allow_guest=False)
def get_material_request(name):
    try:
        doc = frappe.get_doc("Material Request", name)
        return {
            "status": "success",
            "data": {
                "name": doc.name,
                "department": doc.department,
                "requested_by": doc.requested_by,
                "request_date": doc.transaction_date,
                "purpose": doc.purpose,
                "status": doc.status,
                "items": [
                    {
                        "item_code": i.item_code,
                        "item_name": i.item_name,
                        "qty": i.qty,
                        "uom": i.uom,
                        "required_date": i.schedule_date,
                        "remarks": i.description
                    } for i in doc.items
                ]
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Material Request API - Detail")
        frappe.local.response["http_status_code"] = 404
        return {"status": "error", "message": str(e)}



@frappe.whitelist(allow_guest=False)
def update_material_request():
    data = json.loads(frappe.local.form_dict.data)

    try:
        doc = frappe.get_doc("Material Request", data.get("name"))
        doc.department = data.get("department")
        doc.requested_by = data.get("requested_by")
        doc.transaction_date = data.get("request_date")
        doc.purpose = data.get("purpose")
        
        doc.items = []
        for item in data.get("items", []):
            doc.append("items", {
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "qty": item.get("qty"),
                "uom": item.get("uom"),
                "schedule_date": item.get("required_date"),
                "description": item.get("remarks")
            })

        doc.save()
        frappe.db.commit()
        return {"status": "success", "message": "Material Request Updated", "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Material Request API - Update")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}
