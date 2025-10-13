# import frappe
# import json
# from frappe import _
# from erpnext.controllers.accounts_controller import update_child_qty_rate
# from frappe.utils import cstr
# import base64
# from frappe.utils.password import get_decrypted_password
# from frappe.utils import flt


# def authenticate_user():
# 	auth_header = frappe.get_request_header("Authorization")
# 	if not auth_header or not auth_header.startswith("Basic "):
# 		frappe.local.response["http_status_code"] = 401
# 		return None

# 	try:
# 		encoded_token = auth_header.split("Basic ")[1]
# 		decoded = base64.b64decode(encoded_token).decode("utf-8")
# 		api_key, api_secret = decoded.split(":")
# 	except Exception:
# 		frappe.local.response["http_status_code"] = 401
# 		return None

# 	user = frappe.db.get("User", {"api_key": api_key})
# 	if not user or get_decrypted_password("User", user.name, "api_secret") != api_secret:
# 		frappe.local.response["http_status_code"] = 401
# 		return None

# 	return user


# @frappe.whitelist()
# def indent_api():
#     if frappe.request.method != "POST":
#         frappe.throw(_("Only POST method allowed"))

#     # ✅ Authenticate
#     user = authenticate_user()
#     if not user:
#         return {"error": "Unauthorized"}

#     data = frappe.request.get_json()

#     sales_order_name = data.get("name")
#     items = data.get("items", [])

#     if not sales_order_name or not items:
#         frappe.throw(_("Missing 'name' or 'items' in request"))

#     trans_items = []

#     for item in items:
#         item_code = item.get("item_code")
#         if not item_code:
#             continue

#         qty = item.get("qty", 1)
#         item_name = item.get("item_name") or item_code
#         description = item.get("description") or item_code
#         delivery_date = item.get("delivery_date","") 
#         reference_dt = item.get("reference_dt", "")
#         reference_dn = item.get("reference_dn", "")

#         # Fetch item rate
#         rate = get_item_rate(item_code)
#         if rate is None:
#             frappe.throw(f"Rate not found for item: {item_code}")

#         trans_items.append({
#             "item_code": item_code,
#             "item_name": item_name,
#             "description": description,
#             "delivery_date":delivery_date,
#             "qty": qty,
#             "rate": rate,
#             "reference_dt": reference_dt,
#             "reference_dn": reference_dn
#         })

#     # Structure to return and also pass to update_child_qty_rate
#     response_data = {
#         "parent_doctype": "Sales Order",
#         "parent_doctype_name": sales_order_name,
#         "child_docname": "items",
#         "trans_items": trans_items
#     }

#     # Now call update_child_qty_rate
#     result = update_child_qty_rate(
#         parent_doctype=response_data["parent_doctype"],
#         trans_items=json.dumps(response_data["trans_items"]),  # ✅ convert to JSON string
#         parent_doctype_name=response_data["parent_doctype_name"],
#         child_docname="items"
#     )


#     return {
#         "message":"Item Indented Sucessfully" ,
#         "sucess":True,
#         "update_result": response_data
#     }

# def get_item_rate(item_code):
#     """Fetch item rate from Item Price or fallback to Item.standard_rate"""
#     rate = frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, "price_list_rate")
#     if rate:
#         return float(rate)

#     item = frappe.get_doc("Item", item_code)
#     return float(item.standard_rate) if item.standard_rate else None

import frappe
import json
import re
from frappe import _
from erpnext.controllers.accounts_controller import update_child_qty_rate
from frappe.utils import cstr
import base64
from frappe.utils.password import get_decrypted_password
from frappe.utils import flt

from frappe.utils import nowdate



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
	if not user or get_decrypted_password("User", user.name, "api_secret") != api_secret:
		frappe.local.response["http_status_code"] = 401
		return None

	return user


@frappe.whitelist()
def indent_api():
    if frappe.request.method != "POST":
        frappe.throw(_("Only POST method allowed"))

    try:
        data = frappe.request.get_json()
        sales_order_name = data.get("name")
        items = data.get("items", [])

        trans_items = []

        for item in items:
            item_code = item.get("item_code")
            if not item_code:
                continue

            qty = item.get("qty", 1)
            item_name = item.get("item_name") or item_code
            description = item.get("description") or item_code
            reference_dt = item.get("reference_dt", "")
            reference_dn = item.get("reference_dn", "")
            delivery_date = item.get("delivery_date", "")

            # Fetch item rate
            rate = get_item_rate(item_code)
            if rate is None:
                frappe.throw(f"Rate not found for item: {item_code}")

            trans_items.append({
                "item_code": item_code,
                "item_name": item_name,
                "description": description,
                "qty": qty,
                "rate": rate,
                "reference_dt": reference_dt,
                "reference_dn": reference_dn,
                "delivery_date": delivery_date
            })

            # ✅ Lab Order condition check
            if reference_dt == "Service Request" and reference_dn:
                sr_doc = frappe.get_doc(reference_dt, reference_dn)

                if sr_doc.template_dt == "Observation Template":
                    patient = sr_doc.patient
                    encounter = sr_doc.order_group
                    practitioner = sr_doc.practitioner
                    reference_order = sales_order_name
                    template_dn = sr_doc.template_dn
                    # token = getattr(sr_doc, "token", None)

                    # Fetch inpatient_record via patient
                    inpatient_record = frappe.db.get_value("Patient", patient, "inpatient_record")
                    if inpatient_record:
                        inpatient_doc = frappe.get_doc("Inpatient Record", inpatient_record)
                        estimated_cost = inpatient_doc.estimated_cost  # Optional

                    # ✅ Create Lab Order
                    lab_order = frappe.new_doc("Lab Order")
                    lab_order.patient = patient
                    lab_order.encounter = encounter
                    lab_order.healthcare_practitioner = practitioner
                    lab_order.reference_dt = reference_dt
                    lab_order.reference_dn = reference_dn
                    lab_order.reference_order = reference_order
                    # lab_order.token = token
                    lab_order.lab_order_template = template_dn
                    lab_order.billing_status = "Indented"
                    lab_order.status = "Active"
                    lab_order.insert(ignore_permissions=True)

        # ✅ Update child qty and rate in Sales Order
        response_data = {
            "parent_doctype": "Sales Order",
            "parent_doctype_name": sales_order_name,
            "child_docname": "items",
            "trans_items": trans_items
        }

        update_child_qty_rate(
            parent_doctype=response_data["parent_doctype"],
            trans_items=json.dumps(response_data["trans_items"]),
            parent_doctype_name=response_data["parent_doctype_name"],
            child_docname="items"
        )

        return {
            "message": "Item Indented Successfully",
            "success": True,
            "update_result": response_data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Indent API Error")
        return {
            "message": str(e),
            "success": False
        }

# Existing rate fetcher (no changes)
def get_item_rate(item_code):
    rate = frappe.db.get_value("Item Price", {"item_code": item_code, "selling": 1}, "price_list_rate")
    if rate:
        return float(rate)

    item = frappe.get_doc("Item", item_code)
    return float(item.standard_rate) if item.standard_rate else None




# from healthcare.healthcare.doctype.patient_encounter.patient_encounter import (
# 	get_prescription_dates,
# )
# from healthcare.healthcare.doctype.inpatient_medication_order.inpatient_medication_order import add_order_entries

# @frappe.whitelist()
# def indent_medecine_api():
#     if frappe.request.method != "POST":
#         frappe.throw(_("Only POST method allowed"))

#     user = authenticate_user()
#     if not user:
#         return {"error": "Unauthorized"}

#     data = frappe.request.get_json()
#     sales_order_name = data.get("name")
#     items = data.get("items", [])  # drug_prescription

#     if not sales_order_name or not items:
#         frappe.throw(_("Missing 'name' or 'items' in request"))

#     trans_items = []
#     imo_created = False

#     for item in items:
#         drug_code = item.get("drug_code")
#         if not drug_code:
#             continue

#         reference_dt = item.get("reference_dt", "Medication Request")
#         reference_dn = item.get("reference_dn")

#         # Get item rate
#         rate = get_item_rate(drug_code)
#         if rate is None:
#             frappe.throw(f"Rate not found for drug: {drug_code}")

#         # ✅ Compute quantity from dosage and period
#         dosage_str = item.get("dosage", "0")
#         period_str = item.get("period", "0 Day")

#         qty = 1  # default
#         if reference_dt == "Medication Request" and reference_dn:
#             sr_doc = frappe.get_doc(reference_dt, reference_dn)
#             qty = sr_doc.quantity or 1  # fallback to 1 if missing

#         trans_items.append({
            
#             "item_code": drug_code,
#             "item_name": item.get("drug_code") or drug_code,
#             "description": item.get("drug_code") or drug_code,
#             "qty": qty,
#             "rate": rate,
#             "reference_dt": reference_dt,
#             "reference_dn": reference_dn
#         })

#         # ✅ Create Inpatient Medication Order if not already
#         if reference_dt == "Medication Request" and reference_dn:
#             sr_doc = frappe.get_doc(reference_dt, reference_dn)
#             patient = sr_doc.patient
#             encounter = sr_doc.order_group
#             practitioner = sr_doc.practitioner

#             inpatient_record = frappe.db.get_value("Patient", patient, "inpatient_record")
#             if not inpatient_record:
#                 frappe.throw(_("Inpatient Record not found for patient {0}").format(patient))

#             # Create the medication order document
#             imo = frappe.new_doc("Inpatient Medication Order")
#             imo.patient_encounter = encounter
#             imo.patient = patient
#             imo.inpatient_record = inpatient_record
#             imo.practitioner = practitioner
#             imo.company = frappe.defaults.get_user_default("Company")
#             imo.start_date = nowdate()
#             imo.reference_order = sales_order_name
#             imo.reference_dt = reference_dt
#             imo.reference_dn = reference_dn

#             # Add prescription entries using imported `add_order_entries`
#         # Process each drug prescription
#             for pres in data.get("items", []):
#                 add_order_entries(imo, pres)

#             imo.save(ignore_permissions=True)
#             frappe.db.commit()
#             imo_created = True

#     # ✅ Update Sales Order item child table
#     if imo_created:
#         update_child_qty_rate(
#             parent_doctype="Sales Order",
#             trans_items=json.dumps(trans_items),
#             parent_doctype_name=sales_order_name,
#             child_docname="items"
#         )

#     return {
#          "message": "Inpatient Medication Order created" if imo_created else "No Medication Order created",
#         "success": True,
#         "update_result": {
#             "sales_order": sales_order_name,
#             "items_updated": trans_items
#         }
#     }

from collections import defaultdict

@frappe.whitelist()
def indent_medecine_api():
    if frappe.request.method != "POST":
        frappe.throw(_("Only POST method allowed"))

    user = authenticate_user()
    if not user:
        return {"error": "Unauthorized"}

    data = frappe.request.get_json()
    sales_order_name = data.get("name")
    items = data.get("items", [])



    if not sales_order_name or not items:
        frappe.throw(_("Missing 'name' or 'items' in request"))

    sales_order = frappe.get_doc("Sales Order", sales_order_name)
    existing_items = sales_order.items



    trans_items = []
    med_items = []
    imo_created = False

        # ✅ Create a list of existing items
    trans_items = [
        {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "description": row.description,
            "qty": row.qty,
            "rate": row.rate,
            "amount": row.amount,
            "reference_dt": row.reference_dt,
            "reference_dn": row.reference_dn
        }
        for row in existing_items
    ]
    for item in items:
        drug_code = item.get("drug_code")
        reference_dt = item.get("reference_dt")
        reference_dn = item.get("reference_dn")

        if reference_dt == "Medication Request" and reference_dn:
            sr_doc = frappe.get_doc(reference_dt, reference_dn)
            encounter = sr_doc.order_group
            rate = get_item_rate(drug_code) or  0

            ref_doc = frappe.get_doc(reference_dt, reference_dn)
            qty = ref_doc.quantity or 1

            trans_items.append({
                "item_code": drug_code,
                "item_name": drug_code,
                "description": drug_code,
                "qty": qty,
                "rate": rate,
                "reference_dt": reference_dt,
                "reference_dn": reference_dn
            })

    # ✅ Step 1: Group items by Encounter
    encounter_groups = defaultdict(list)

    for item in items:
        drug_code = item.get("drug_code")
        reference_dt = item.get("reference_dt")
        reference_dn = item.get("reference_dn")

        if reference_dt == "Medication Request" and reference_dn:
            sr_doc = frappe.get_doc(reference_dt, reference_dn)
            encounter = sr_doc.order_group
            item["encounter"] = encounter  # Store for later
            encounter_groups[encounter].append(item)
        else:
            item["encounter"] = None
            encounter_groups[None].append(item)

    # ✅ Step 2: Process each Encounter group
    for encounter, item_group in encounter_groups.items():
        if not encounter:
            continue  # skip for now if no encounter

        # Get common info from first item
        first_item = item_group[0]
        ref_doc = frappe.get_doc(first_item.get("reference_dt"), first_item.get("reference_dn"))
        patient = ref_doc.patient
        practitioner = ref_doc.practitioner
        inpatient_record = frappe.db.get_value("Patient", patient, "inpatient_record")

        if not inpatient_record:
            frappe.throw(_("Inpatient Record not found for patient {0}").format(patient))

        # Check if IMO exists already
        # existing_imo_name = frappe.db.get_value("Inpatient Medication Order", {"patient_encounter": encounter})
        # if existing_imo_name:
        #     frappe.msgprint(f"Inpatient Medication Order already exists for encounter {encounter}")
        #     continue

        # ✅ Create new IMO
        imo = frappe.new_doc("Inpatient Medication Order")
        imo.patient_encounter = encounter
        imo.patient = patient
        imo.inpatient_record = inpatient_record
        imo.practitioner = practitioner
        imo.company = frappe.defaults.get_user_default("Company")
        imo.start_date = nowdate()
        imo.reference_order = sales_order_name
        imo.reference_dt = first_item.get("reference_dt")
        imo.reference_dn = first_item.get("reference_dn")

        # Add all prescriptions in that group
        for pres in item_group:
            drug_code = pres.get("drug_code")
            # item_code = pres.get("item_code") get_item_rate(item_code) or
            rate = get_item_rate(drug_code) or  0

            ref_doc = frappe.get_doc(pres.get("reference_dt"), pres.get("reference_dn"))
            qty = ref_doc.quantity or 1

            # med_items.append({
            #     "item_code": drug_code,
            #     "item_name": drug_code,
            #     "description": drug_code,
            #     "qty": qty,
            #     "rate": rate,
            #     "reference_dt": pres.get("reference_dt"),
            #     "reference_dn": pres.get("reference_dn")
            # })
            # trans_items.extend(med_items)
            # Add to IMO
            add_order_entries(imo, pres)

        imo.save(ignore_permissions=True)
        frappe.db.commit()
        imo_created = True




    # ✅ Update Sales Order items
    if imo_created:
        update_child_qty_rate(
            parent_doctype="Sales Order",
            trans_items=json.dumps(trans_items),
            parent_doctype_name=sales_order_name,
            child_docname="items"
        )

    return {
        "message": "Inpatient Medication Order created" if imo_created else "No new IMO created",
        "success": True,
        "update_result": {
            "sales_order": sales_order_name,
            "items_updated": trans_items
        }
    }


import frappe
from frappe.utils import getdate, add_days
from frappe.model.document import Document

@frappe.whitelist()
def add_order_entries(imo_doc, order):
    """
    Adds medication order entries to the given Inpatient Medication Order document.
    """

    if not order.get("drug_code"):
        return

    # Get dosage schedule (e.g., "1-0-1")
    dosage = frappe.get_doc("Prescription Dosage", order.get("dosage"))

    # duration_doc = frappe.get_doc("Prescription Duration", order.get("period"))
    dates = get_prescription_dates(order.get("period"), frappe.utils.nowdate())


    for date in dates:
        for dose in dosage.dosage_strength:
            entry = imo_doc.append("medication_orders", {})
            entry.drug = order.get("drug_code")
            entry.drug_name = frappe.db.get_value("Item", order.get("drug_code"), "item_name")
            entry.dosage = dose.strength
            entry.dosage_form = order.get("dosage_form")
            entry.date = date
            entry.time = dose.strength_time
            entry.instructions = order.get("instructions", "")

    # Set IMO end_date to the last prescription date
    imo_doc.end_date = dates[-1] if dates else imo_doc.start_date


def get_prescription_dates(period, start_date):
	prescription_duration = frappe.get_doc("Prescription Duration", period)
	days = prescription_duration.get_days()
	dates = [start_date]
	for i in range(1, days):
		dates.append(add_days(getdate(start_date), i))
	return dates

