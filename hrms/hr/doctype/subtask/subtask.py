# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe import _, throw
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import now_datetime, get_datetime


class SubTask(Document):
	def validate(self):
		print("validate subtask called")
		self.validate_subtask_name()
		self.track_time_status_change()
		ensure_employee_in_maintask_child_table(self)


	def validate_subtask_name(self):
		self.maintask = frappe.db.get_value("Tasks",{"name": self.tasks}, "maintask" )
		self.maintask_name = frappe.db.get_value("MainTask", {"name": self.maintask}, "maintask_name")
		self.tasks_name = frappe.db.get_value("Tasks", {"name": self.tasks}, "task_name")
		self.pic_subtask_name = frappe.db.get_value("Employee", {"name": self.pic_subtask}, "employee_name")
		self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")
		if self.status == "Open":
			self.subtask_open_date = datetime.strptime(self.creation, "%Y-%m-%d %H:%M:%S.%f").date() if isinstance(
				self.creation, str) else self.creation.date()
		if self.status == "In Progress":
			self.subtask_start_date = datetime.strptime(now_datetime(), "%Y-%m-%d %H:%M:%S.%f").date() if isinstance(
				now_datetime(), str) else now_datetime().date()
		if self.status == "Done":
			self.subtask_done_date = datetime.strptime(now_datetime(), "%Y-%m-%d %H:%M:%S.%f").date() if isinstance(
				now_datetime(), str) else now_datetime().date()
		if self.unit_target_time == "Hours":
			self.target_time_minutes = self.target_time * 60
		else:
			self.target_time_minutes = self.target_time

		if self.flags.updater_reference:
			print('self.flags.updater_reference triggered in validate')
			if self.flags.updater_reference.get("doctype") == "Auto Repeat":
				print('doctype auto repeat triggered in validate')
				reference = frappe.get_doc("Auto Repeat", self.auto_repeat)
				ref_doc = frappe.get_doc(reference.reference_doctype, reference.reference_document)
				self.created_by = ref_doc.owner
				self.created_by = frappe.db.get_value("Employee", {"user_id": ref_doc.owner}, "employee_name")
				self.owner = ref_doc.owner
				self.attachment = None
				self.submission_text = None
				if self.status != "Open":
					self.status = "Open"
					
	def track_time_status_change(self):
      # hanya proses jika bukan dokumen baru & status benar2 berubah
		if self.get('__islocal') or not self.has_value_changed('status'):
			return
		# if not self.get('__islocal') and self.has_value_changed('status'):
		previous_doc = self.get_doc_before_save()
		previous_status = previous_doc.status if previous_doc else None
		now = now_datetime()

		# --- override: jika perubahan datang dari Tasks (propagation)
		from_parent = bool(self.flags.get('from_parent_propagation'))
  
		if self.status == "In Progress":
			self.last_in_progress_timestamp = now

		elif self.status in ("Pause", "Done"):
			if not self.last_in_progress_timestamp:
       			# jika datang dari Tasks dan sebelumnya bukan In Progress,
                # izinkan skip tanpa menambah waktu & tanpa error
				if from_parent and previous_status in ("Open", "Cancel", None):
					# tidak ada waktu yang ditambahkan; langsung lolos
					# (opsional) kalau mau set 0 menit eksplisit, biarkan total_time apa adanya
					self.last_in_progress_timestamp = 0
					self.total_time = 0
					return

				# selain itu, tetap enforce aturan normal
				frappe.throw(
					f"Can't change status to '{self.status}', you have to change it to 'In Progress' first."
				)
			duration = int((now - get_datetime(self.last_in_progress_timestamp)).total_seconds() / 60)  
			self.total_time = (self.total_time or 0) + duration
			self.last_in_progress_timestamp = None

def update_fields(doc, method):
	if frappe.flags.in_update:
		# frappe.msgprint(f"In update SubTask")
		return
	frappe.flags.in_update = True
	print("update fields subtask called")
	task = frappe.get_doc("Tasks", doc.tasks)
	maintask = frappe.get_doc("MainTask", task.maintask)
	doc.maintask = maintask.name
	if doc.status == 'Open':
		doc.subtask_done_date = None
		doc.save()
		# frappe.db.set_value("SubTask", doc.name, "subtask_done_date", None)

	frappe.flags.in_update = False


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
	user_id = user or frappe.session.user

	roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
 
	if "System Manager" in roles and user_id == "Administrator":
		return ""

	employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")
	parent_mteam = frappe.get_all(
		"MainTask Team",
		filters={"employee": employee_id},
		pluck="parent"
	)

	parent_assign_by = frappe.get_all(
		"MainTask Assign By",
		filters={"employee": employee_id},
		pluck="parent"
	)

	if not employee_id:
		return "1=0"

	maintask_ids = "', '".join(parent_mteam)

	assign_by_maintask_ids = "', '".join(parent_assign_by)

	return f"""
		(`tabSubTask`.`pic_subtask` = '{employee_id}'
		OR `tabSubTask`.`owner` = '{user_id}'
		OR `tabSubTask`.`tasks` IN (
			SELECT `name` FROM `tabTasks` WHERE `owner` = '{user_id}'
		) OR `tabSubTask`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE `assigned_by` = '{employee_id}' OR `owner` = '{user_id}') OR `tabSubTask`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE name IN ('{maintask_ids}'))  OR `tabSubTask`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE name IN ('{assign_by_maintask_ids}')))
	"""


def has_permission(doc, ptype, user):
	print("has permission subtask called")

	if user == "Administrator":
		return True

	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
	if not employee_id:
		return False

	parent_assign_by = frappe.get_all(
		"MainTask Assign By",
		filters={"employee": employee_id},
		pluck="parent"
	)
 
	parent_mteam = frappe.get_all(
		"MainTask Team",
		filters={"employee": employee_id},
		pluck="parent"
	)
    
	if ptype in ("read", None) and (doc.maintask in parent_mteam or doc.maintask in parent_assign_by):
		return True

	employee = frappe.get_doc("Employee", employee_id)
	tasks = frappe.get_doc("Tasks", doc.tasks)
	
	parent_task_pic = frappe.get_all(
		"Task PIC",
		filters={"employee": employee_id},
		pluck="parent"
	)

	if ptype == "delete":
		maintask = frappe.get_doc("MainTask", doc.maintask)
		if doc.pic_subtask == employee_id and doc.tasks not in parent_task_pic and maintask.owner != user and doc.maintask not in parent_assign_by:
			frappe.throw(f"{employee.employee_name} is pic subtask only and not allowed to deleting {doc.subtask_name} subtask.",
							frappe.PermissionError)
			return False
		check_evaluated = frappe.get_value("Evaluation", {"subtask": doc.name}, "subtask")
		if check_evaluated:
			frappe.throw(_(f"Sorry {employee.employee_name} this subtask is evaluated, you can't delete it.",
							frappe.PermissionError))
			return False
	elif doc.pic_subtask == employee_id and ptype != "delete":
		return True

	if doc.tasks:
		owner_task = tasks.owner
		print(f'doc tasks {doc.tasks}, parent_task_pic {parent_task_pic}')
		if owner_task == frappe.session.user or doc.tasks in parent_task_pic:
			return True

	frappe.throw(f"{employee.employee_name} is not allowed to accessing {doc.subtask_name} subtask.",
					frappe.PermissionError)
	return False

def _lock_maintask_for_maintask_update(maintask_id: str):
    """Opsional: cegah duplikasi bila ada save paralel."""
    frappe.db.sql("SELECT name FROM `tab{}` WHERE name=%s FOR UPDATE".format("MainTask"), maintask_id)

def _append_child_table_maintask_row_if_missing(parent_doc, employee_id: str, employee_name: str | None, child):
    
    rows = getattr(parent_doc, child, []) or []
    for r in rows:
        if getattr(r, "employee", None) == employee_id:
            return False 

    newr = parent_doc.append(child, {})
    setattr(newr, "employee", employee_id)
    if "employee_name":
        if employee_name:
            setattr(newr, "employee_name", employee_name)
        else:
            db_name = frappe.db.get_value("Employee", employee_id, "employee_name")
            setattr(newr, "employee_name", db_name)

    return True

def ensure_employee_in_maintask_child_table(doc: Document | str):
    
    if isinstance(doc, str):
        doc = frappe.get_doc("SubTask", doc)

    emp_id = getattr(doc, "pic_subtask", None)
    parent_id = getattr(doc, "maintask", None)

    if not emp_id or not parent_id:
        return 

    _lock_maintask_for_maintask_update(parent_id)

    parent = frappe.get_doc("MainTask", parent_id)
    emp_name = getattr(doc, "pic_subtask_name", None)
    
    emp_reports_to = frappe.db.get_value("Employee", emp_id, "reports_to")
    emp_reports_to_name = frappe.db.get_value("Employee", emp_reports_to, "employee_name") if emp_reports_to else None

    team_added = _append_child_table_maintask_row_if_missing(parent, emp_id, emp_name, "team")
    assign_by_added = _append_child_table_maintask_row_if_missing(parent, emp_reports_to, emp_reports_to_name, "assign_by") if emp_reports_to else False

    if team_added & assign_by_added:
        parent.save(ignore_permissions=True)
        frappe.msgprint(
            f"Employee <b>{frappe.utils.escape_html(emp_name or emp_id)}</b> "
            f"added to Team MainTask <b>{frappe.utils.escape_html(parent.maintask_name)}</b>.",
            f"and Employee <b>{frappe.utils.escape_html(emp_reports_to_name or emp_reports_to)}</b> "
            f"added to Assign By MainTask <b>{frappe.utils.escape_html(parent.maintask_name)}</b>.",
            alert=True
        )
    elif team_added:
        parent.save(ignore_permissions=True)
        frappe.msgprint(
			f"Employee <b>{frappe.utils.escape_html(emp_name or emp_id)}</b> "
			f"added to Team MainTask <b>{frappe.utils.escape_html(parent.maintask_name)}</b>.",
			alert=True
		)
    elif assign_by_added:
        parent.save(ignore_permissions=True)
        frappe.msgprint(
            f"Employee <b>{frappe.utils.escape_html(emp_reports_to_name or emp_reports_to)}</b> "
            f"added to Assign By MainTask <b>{frappe.utils.escape_html(parent.maintask_name)}</b>.",
            alert=True
        )

@frappe.whitelist()
def user_edit_subtask(subtask_name):
	if frappe.session.user == "Administrator":
		return "admin"

	doc = frappe.get_doc("SubTask", subtask_name)
	employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")

	if not employee_id:
		return "none"

	if doc.tasks:
		tasks = frappe.get_doc("Tasks", doc.tasks)
		owner_task = tasks.owner

		parent_task_pic = frappe.get_all(
			"Task PIC",
			filters={"employee": employee_id},
			pluck="parent"
		)

		print(f'{type(parent_task_pic)} type, parent_task_pic value {parent_task_pic}')
		if tasks.name in parent_task_pic:
			return "task_pics"

		if doc.pic_subtask == employee_id:
			return "pic_subtask"
		if owner_task == frappe.session.user:
			return "owner_task"

	return "none"


@frappe.whitelist()
def get_employees_by_team(doctype, txt, searchfield, start, page_len, filters):
	tasks = filters.get("tasks")
	if not tasks:
		return []
	task_doc = frappe.get_doc("Tasks", tasks)
	maintask = task_doc.maintask

	employees = frappe.db.sql("""
							  SELECT e.name, e.employee_name
							  FROM `tabEmployee` e
									   JOIN `tabUser` u ON u.name = e.user_id
									   JOIN `tabMainTask Team` mteam ON mteam.employee = e.name
									   JOIN `tabMainTask` mt ON mt.name = mteam.parent
							  WHERE mt.name = %(maintask)s
								AND e.status = 'Active'
								AND (e.name LIKE %(txt)s OR e.employee_name LIKE %(txt)s)
							  GROUP BY e.name
							  ORDER BY e.employee_name
								  LIMIT %(page_len)s
							  OFFSET %(start)s
							  """, {
		"maintask": maintask,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len
	})
	return employees


@frappe.whitelist()
def get_task_with_same_pic(doctype, txt, searchfield, start, page_len, filters):
	user = frappe.session.user
	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

	conditions = ""
	if user != "Administrator":
		conditions = "WHERE tp.employee = %(employee_id)s AND t.status = 'Open' AND (t.name LIKE %(txt)s OR t.task_name LIKE %(txt)s)"

	tasks = frappe.db.sql(f"""
		SELECT t.name, t.task_name
		FROM `tabTasks` t
		JOIN `tabTask PIC` tp ON tp.parent = t.name
		{conditions}
		GROUP BY t.name
		ORDER BY t.name
		LIMIT %(page_len)s OFFSET %(start)s
	""", {
		"employee_id": employee_id,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})
	return tasks

@frappe.whitelist()
def button_evaluation_subtask(subtask):
	user = frappe.session.user
	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
	subtask = frappe.get_doc("SubTask", subtask)
	evaluation_subtask = frappe.get_value("Evaluation", {"subtask": subtask.name}, "name")
	# task = frappe.get_doc("Tasks", subtask.tasks)
	maintask = frappe.get_doc("MainTask", subtask.maintask)
	roles = frappe.get_all("Has Role", filters={"parent": user}, pluck="role")
	parent_task_pic = frappe.get_all(
			"Task PIC",
			filters={"employee": employee_id},
			pluck="parent"
		)
	print(f"User: {user}, Maintask Owner: {maintask.owner}, parent_task_pic: {parent_task_pic}, Roles: {roles}")
 
	if maintask.owner == user and subtask.status == "Done":
		return "maintask_owner_done"
	if subtask.tasks in parent_task_pic and ('Leader' in roles or 'Manager' in roles or 'Supervisor' in roles) and subtask.status == "Done":
		return "pic_task_done"
	if "System Manager" in roles:
		return "system_manager_done"
	if subtask.status == "Close" and evaluation_subtask:
		return {
			"status": "Close",
			"evaluation_name": evaluation_subtask
		}

	return False

@frappe.whitelist()  
def subtask_value_agent_suggestion(title, description):
    try:
        url = "http://10.12.1.148:9968/classify-skillset"
        payload = {
            "task": title,
            "description": description
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Agent Subtask Value Suggestion Error")
        return {"error": str(e)}
    
@frappe.whitelist()  
def pic_subtask_agent_suggestion(title, description):
    try:
        url = "http://10.12.1.148:9968/classify-person"
        payload = {
            "task": title,
            "description": description
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Agent PIC Subtask Suggestion Error")
        return {"error": str(e)}
    
@frappe.whitelist()
def get_employee_from_agent_data(name: str, status: str = "Active", limit: int = 10):
    # cari employee_name yang mengandung keyword
    if not name:
        return []

    rows = frappe.get_all(
        "Employee",
        filters={"status": status},
        or_filters=[["employee_name", "like", f"%{name}%"]],
        fields=["name", "employee_name", "department", "company"],
        limit_page_length=limit,
    )
    return rows