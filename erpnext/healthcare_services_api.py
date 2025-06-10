import base64
import frappe
from frappe.utils.password import get_decrypted_password

# ------------------- Authentication ---------------------
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
        frappe.log_error(frappe.get_traceback(), "Auth Decode Error")
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


# ------------------- GET Healthcare Services ---------------------
@frappe.whitelist(allow_guest=True)
def get_healthcare_services():
    if frappe.request.method != "GET":
        frappe.local.response["http_status_code"] = 405
        return {"message": "Only GET allowed", "success": False}

    if not authenticate_user():
        return {"message": "Unauthorized", "success": False}

    patient = frappe.local.form_dict.get("patient")
    if not patient:
        frappe.local.response["http_status_code"] = 400
        return {"message": "Missing patient ID", "success": False}

    try:
        services = []

        # 1. From Patient Appointment
        appointments = frappe.get_all("Patient Appointment",
            filters={"patient": patient, "invoiced": 0},
            fields=["name","billing_item"]
        )
        for appt in appointments:
            services.append({
                "service": appt.billing_item,
                "reference_name": appt.name,
                "reference_type": "Patient Appointment"
            })

        # 2. From Patient Encounter
        encounters = frappe.get_all("Patient Encounter",
            filters={"patient": patient, "invoiced": 0},
            fields=["name"]
        )
        for enc in encounters:
            services.append({
                "service": "Inpatient Visit Charge",
                "reference_name": enc.name,
                "reference_type": "Patient Encounter"
            })

        # 3. From Inpatient Occupancy
      # 3. From Inpatient Occupancy
        occupancies = frappe.db.sql("""
            SELECT io.name AS occupancy_name,
                su.service_unit_type,
                su.name AS service_unit_name
            FROM `tabInpatient Occupancy` io
            JOIN `tabInpatient Record` ir ON io.parent = ir.name
            LEFT JOIN `tabHealthcare Service Unit` su ON io.service_unit = su.name
            WHERE ir.patient = %s AND io.invoiced = 0
        """, (patient,), as_dict=True)

        for occ in occupancies:
            services.append({
                "service": occ.service_unit_type or "Unknown",
                "reference_name": occ.occupancy_name,
                "reference_type": "Inpatient Occupancy"
            })




        # 4. From Healthcare Service Request
        service_requests = frappe.get_all("Service Request",
            filters={"patient": patient, "billing_status": "Pending"},
            fields=["name", "template_dn"]
        )
        for sr in service_requests:
            services.append({
                "service": sr.template_dn,
                "reference_name": sr.name,
                "reference_type": "Service Request"
            })

        return {
            "message": "Fetched successfully",
            "success": True,
            "data": services
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Healthcare Services")
        return {"message": str(e), "success": False}
