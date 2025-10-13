# -*- coding: utf-8 -*-
import frappe
import base64
from frappe.utils.data import cint

# ------------------------------
# ✅ Authentication Helper
# ------------------------------
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

    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    if not user:
        frappe.local.response["http_status_code"] = 401
        return None

    stored_secret = frappe.utils.password.get_decrypted_password("User", user, "api_secret")
    if stored_secret != api_secret:
        frappe.local.response["http_status_code"] = 401
        return None

    frappe.set_user(user)
    return user


# ------------------------------
# ✅ CREATE Shipping Rule
# ------------------------------
@frappe.whitelist(allow_guest=True)
def create_shipping_rule():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        rule = frappe.new_doc("Shipping Rule")
        rule.label = data.get("label")
        rule.disabled = cint(data.get("disabled", 0))
        rule.shipping_rule_type = data.get("shipping_rule_type")
        rule.company = data.get("company")
        rule.account = data.get("account")
        rule.cost_center = data.get("cost_center")
        rule.calculate_based_on = data.get("calculate_based_on") or "Fixed"
        rule.shipping_amount = data.get("shipping_amount") or 0



        # Append countries table if provided
        countries = data.get("countries", [])
        for c in countries:
            rule.append("countries", {
                "country": c.get("country")
            })

        rule.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Shipping Rule created successfully", "shipping_rule_id": rule.name}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Shipping Rule API")
        return {"error": str(e)}


# ------------------------------
# ✅ GET ALL Shipping Rules
# ------------------------------
@frappe.whitelist(allow_guest=True)
def get_all_shipping_rules():
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        rules = frappe.get_all(
            "Shipping Rule",
            fields=["name", "label", "shipping_rule_type", "company", "disabled"],
            order_by="creation desc"
        )
        return rules
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Shipping Rules API")
        return {"error": str(e)}


# ------------------------------
# ✅ GET Shipping Rule by ID
# ------------------------------
@frappe.whitelist(allow_guest=True)
def get_shipping_rule_by_id(name):
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        rule = frappe.get_doc("Shipping Rule", name)
        data = rule.as_dict()

        

        # Get countries table
        data["countries"] = [c.as_dict() for c in rule.countries]

        return data
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Shipping Rule By ID API")
        return {"error": str(e)}


# ------------------------------
# ✅ UPDATE Shipping Rule
# ------------------------------
@frappe.whitelist(allow_guest=True)
def update_shipping_rule(rule_id):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        rule = frappe.get_doc("Shipping Rule", rule_id)
        rule.update({
            "label": data.get("label", rule.label),
            "disabled": cint(data.get("disabled", rule.disabled)),
            "shipping_rule_type": data.get("shipping_rule_type", rule.shipping_rule_type),
            "company": data.get("company", rule.company),
            "account": data.get("account", rule.account),
            "cost_center": data.get("cost_center", rule.cost_center),
            "calculate_based_on": data.get("calculate_based_on", rule.calculate_based_on),
            "shipping_amount": data.get("shipping_amount", rule.shipping_amount),
        })

        # Update conditions
        if "conditions" in data:
            rule.set("conditions", [])
            for cond in data["conditions"]:
                rule.append("conditions", {
                    "condition_type": cond.get("condition_type"),
                    "value": cond.get("value"),
                    "description": cond.get("description")
                })

        # Update countries
        if "countries" in data:
            rule.set("countries", [])
            for c in data["countries"]:
                rule.append("countries", {"country": c.get("country")})

        rule.save(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Shipping Rule updated successfully", "shipping_rule_id": rule.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Shipping Rule API")
        return {"error": str(e)}


# ------------------------------
# ✅ DELETE Shipping Rule
# ------------------------------
@frappe.whitelist(allow_guest=True)
def delete_shipping_rule(rule_id):
    if frappe.request.method != "DELETE":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only DELETE method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        frappe.delete_doc("Shipping Rule", rule_id, ignore_permissions=True)
        frappe.db.commit()
        return {"message": f"Shipping Rule {rule_id} deleted successfully"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Shipping Rule API")
        return {"error": str(e)}
