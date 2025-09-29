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


@frappe.whitelist(allow_guest=True)
def listPrice():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:

        pricelist = frappe.get_all(
            "Price List",
            fields=[
             "*"
            ],
            order_by="creation desc",
        )

     
        return {
            "message": pricelist
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "List Price List")
        frappe.local.response["http_status_code"] = 500
        return {"error": str(e)}

