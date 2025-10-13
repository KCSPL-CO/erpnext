# -*- coding: utf-8 -*-
import base64
import frappe
import json

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
# ✅ CREATE Supplier
# ------------------------------
import frappe
from frappe import _
from frappe.utils.data import cint

@frappe.whitelist(allow_guest=True)
def create_supplier():
    if frappe.request.method != "POST":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only POST method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        # ------------------- SUPPLIER -------------------
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = data.get("supplier_name")
        supplier.supplier_type = data.get("supplier_type") or "Company"
        supplier.supplier_group = data.get("supplier_group") or "All Supplier Groups"
        supplier.supplier_details = data.get("supplier_details")
        supplier.tax_id = data.get("tax_id")
        supplier.country = data.get("country") or "India"
        supplier.website = data.get("website")
        supplier.represents_company = data.get("represents_company")
        supplier.is_transporter = cint(data.get("is_transporter", 0))
        supplier.is_internal_supplier = cint(data.get("is_internal_supplier", 0))
        supplier.default_currency = data.get("default_currency") or "INR"
        supplier.default_bank_account = data.get("default_bank_account")
        supplier.default_price_list = data.get("default_price_list")
        supplier.tax_category = data.get("tax_category")
        supplier.tax_withholding_category = data.get("tax_withholding_category")
        supplier.allow_purchase_invoice_creation_without_purchase_order = cint(data.get("allow_purchase_invoice_creation_without_purchase_order", 0))
        supplier.allow_purchase_invoice_creation_without_purchase_receipt = cint(data.get("allow_purchase_invoice_creation_without_purchase_receipt", 0))
        supplier.is_frozen = cint(data.get("is_frozen", 0))
        supplier.on_hold = cint(data.get("on_hold", 0))
        supplier.hold_type = data.get("hold_type")
        supplier.release_date = data.get("release_date")

        # --- Accounts Table ---
        accounts = data.get("accounts", [])
        if accounts:
            for acc in accounts:
                supplier.append("accounts", {
                    "company": acc.get("company"),
                    "account": acc.get("account"),
                    "default_currency": acc.get("default_currency")
                })

        # --- Insert Supplier first ---
        supplier.insert(ignore_permissions=True)
        frappe.db.commit()
        supplier_id = supplier.name

        # ------------------- ADDRESS -------------------
        address_name = None
        address_data = data.get("address")
        if address_data:
            address = frappe.new_doc("Address")
            address.address_title = address_data.get("address_title") or supplier_id
            address.address_type = address_data.get("address_type") or "Billing"
            address.address_line1 = address_data.get("address_line1")
            address.address_line2 = address_data.get("address_line2")
            address.city = address_data.get("city")
            address.state = address_data.get("state")
            address.pincode = address_data.get("pincode")
            address.country = address_data.get("country") or "India"
            address.is_primary_address = cint(address_data.get("is_primary_address", 1))
            address.is_shipping_address = cint(address_data.get("is_shipping_address", 0))
            address.append("links", {"link_doctype": "Supplier", "link_name": supplier_id})
            address.insert(ignore_permissions=True)
            address_name = address.name

        # ------------------- CONTACT -------------------
        contact_name = None
        contact_data = data.get("contact")
        if contact_data:
            contact = frappe.new_doc("Contact")
            contact.first_name = contact_data.get("first_name")
            contact.last_name = contact_data.get("last_name")
            contact.email_id = contact_data.get("email_id")
            contact.mobile_no = contact_data.get("mobile_no")
            contact.phone = contact_data.get("phone")
            contact.append("links", {"link_doctype": "Supplier", "link_name": supplier_id})
            contact.insert(ignore_permissions=True)
            contact_name = contact.name

        # ------------------- LINK PRIMARY ADDRESS & CONTACT -------------------
        if address_name:
            supplier.db_set("supplier_primary_address", address_name)
        if contact_name:
            supplier.db_set("supplier_primary_contact", contact_name)

        frappe.db.commit()
        return {"message": "Supplier created successfully", "supplier_id": supplier_id}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Supplier API")
        return {"error": str(e)}


# ------------------------------
# ✅ GET ALL Suppliers
# ------------------------------
@frappe.whitelist(allow_guest=True)
def get_all_suppliers():

    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}
    
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        suppliers = frappe.get_all(
            "Supplier",
            fields=["name", "supplier_name", "supplier_group", "supplier_type", "country", "disabled"],
            order_by="creation desc"
        )
        return suppliers
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Suppliers API")
        return {"error": str(e)}


# ------------------------------
# ✅ GET Supplier by ID
# ------------------------------
@frappe.whitelist(allow_guest=True)
def get_supplier_by_id(supplier_id):

    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only GET method allowed"}
    
    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        supplier = frappe.get_doc("Supplier", supplier_id)
        data = supplier.as_dict()

        # Fetch linked Address
        address = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Supplier", "link_name": supplier_id, "parenttype": "Address"},
            "parent"
        )
        if address:
            data["address"] = frappe.get_doc("Address", address).as_dict()

        # Fetch linked Contact
        contact = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Supplier", "link_name": supplier_id, "parenttype": "Contact"},
            "parent"
        )
        if contact:
            data["contact"] = frappe.get_doc("Contact", contact).as_dict()

        return data
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Supplier By ID API")
        return {"error": str(e)}


# ------------------------------
# ✅ UPDATE Supplier
# ------------------------------
@frappe.whitelist(allow_guest=True)
def update_supplier(supplier_id):
    if frappe.request.method != "PUT":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only PUT method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    try:
        supplier = frappe.get_doc("Supplier", supplier_id)
        supplier.update({
            "supplier_name": data.get("supplier_name", supplier.supplier_name),
            "supplier_group": data.get("supplier_group", supplier.supplier_group),
            "supplier_type": data.get("supplier_type", supplier.supplier_type),
            "country": data.get("country", supplier.country),
            "tax_id": data.get("tax_id", supplier.tax_id),
        })
        supplier.save(ignore_permissions=True)
        frappe.db.commit()

        # Update Address
        address_data = data.get("address")
        if address_data:
            address_name = frappe.db.get_value(
                "Dynamic Link",
                {"link_doctype": "Supplier", "link_name": supplier_id, "parenttype": "Address"},
                "parent"
            )
            if address_name:
                address = frappe.get_doc("Address", address_name)
                address.update({
                    "address_line1": address_data.get("line1"),
                    "address_line2": address_data.get("line2"),
                    "city": address_data.get("city"),
                    "state": address_data.get("state"),
                    "pincode": address_data.get("pincode"),
                    "country": address_data.get("country") or "India",
                })
                address.save(ignore_permissions=True)

        # Update Contact
        contact_data = data.get("contact")
        if contact_data:
            contact_name = frappe.db.get_value(
                "Dynamic Link",
                {"link_doctype": "Supplier", "link_name": supplier_id, "parenttype": "Contact"},
                "parent"
            )
            if contact_name:
                contact = frappe.get_doc("Contact", contact_name)
                contact.update({
                    "email_id": contact_data.get("email"),
                    "phone": contact_data.get("phone"),
                    "mobile_no": contact_data.get("mobile"),
                })
                contact.save(ignore_permissions=True)

        frappe.db.commit()
        return {"message": "Supplier updated successfully", "supplier_id": supplier_id}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Supplier API")
        return {"error": str(e)}


# ------------------------------
# ✅ DELETE Supplier
# ------------------------------
@frappe.whitelist(allow_guest=True)
def delete_supplier(supplier_id):
    if frappe.request.method != "DELETE":
        frappe.local.response["http_status_code"] = 405
        return {"error": "Only DELETE method allowed"}

    if not authenticate_user():
        return {"error": "Unauthorized"}

    try:
        frappe.delete_doc("Supplier", supplier_id, ignore_permissions=True)
        frappe.db.commit()
        return {"message": f"Supplier {supplier_id} deleted successfully"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Supplier API")
        return {"error": str(e)}
