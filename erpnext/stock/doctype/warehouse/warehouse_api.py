import frappe
from frappe import _
from frappe.utils import nowdate
import base64

 
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

@frappe.whitelist(allow_guest=True)
def listWarehouse():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        warehouse = frappe.get_all(
            "Warehouse",
            fields=["*"],
            order_by="creation desc",
        )
        return {
            "message": warehouse,
           
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Warehouse")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}



@frappe.whitelist(allow_guest=True)
def listWarehouseType():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        warehouseType = frappe.get_all(
            "Warehouse Type",
            fields=["*"],
            order_by="creation desc",
        )
        return {
            "message": warehouseType,
           
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Warehouse Type")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}

# ---------------- Get Warehouse by ID ----------------
@frappe.whitelist(allow_guest=True)
def getWarehouseById():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        data = frappe.form_dict  # reads JSON body
        warehouse_id = data.get("id")  # ID passed in body

        if not warehouse_id:
            return {"error": "Warehouse ID is required"}

        warehouse = frappe.get_doc("Warehouse", warehouse_id)
        return {"message": warehouse.as_dict()}

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"error": "Warehouse not found"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Warehouse By Id")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}


# ---------------- Create Warehouse (all fields) ----------------
@frappe.whitelist(allow_guest=True)
def createWarehouse():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        data = frappe.form_dict  # request JSON body

        # Create doc dynamically with all fields provided in body
        warehouse_doc = frappe.get_doc({
            "doctype": "Warehouse",
            **data  # unpack all fields from request
        })

        warehouse_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"message": warehouse_doc.as_dict()}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Warehouse (All Fields)")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}