# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe import _, throw
from frappe.model.document import Document
from datetime import datetime, timedelta
from frappe.utils import now_datetime, get_datetime


class SubTask(Document):
	def validate(self):
		print(f"validate subtask {self.name} owner {self.owner}")
		self._set_derived_fields()
		self._handle_status()	
		ensure_employee_in_maintask_child_table(self)
	
	def before_insert(self):
		print(f"before insert subtask with status {self.status}")
		self._reset_for_new_subtask()
		tasks = frappe.get_doc("Tasks", self.tasks)
		if tasks.status not in ("Open", "In Progress"):
			frappe.throw(_("Cannot create SubTask because the parent Task '{0}' is not Open or In Progress.").format(tasks.task_name))

	def _set_derived_fields(self):
		self.maintask = frappe.db.get_value("Tasks", self.tasks, "maintask")
		self.maintask_name = frappe.db.get_value("MainTask", self.maintask, "maintask_name")
		self.tasks_name = frappe.db.get_value("Tasks", self.tasks, "task_name")
		self.pic_subtask_name = frappe.db.get_value("Employee", self.pic_subtask, "employee_name")
		self.created_by = frappe.db.get_value("Employee", {"user_id": self.owner}, "employee_name")
		if self.unit_target_time == "Hours":
			self.target_time_minutes = self.target_time * 60
		else:
			self.target_time_minutes = self.target_time

		# auto repeat
		if self.flags.updater_reference and self.flags.updater_reference.get("doctype") == "Auto Repeat":
			reference = frappe.get_doc("Auto Repeat", self.auto_repeat)
			ref_doc = frappe.get_doc(reference.reference_doctype, reference.reference_document)
			self.owner = ref_doc.owner
			self.created_by = frappe.db.get_value("Employee", {"user_id": ref_doc.owner}, "employee_name")
			self._reset_for_new_subtask()

	def _reset_for_new_subtask(self):
		self.status = "Open"
		self.subtask_open_date = get_datetime(self.creation)
		self.submission_text = None
		self.attachment = None
		self.total_time = None
		self.last_in_progress_timestamp = None
		self.subtask_start_date = None
		self.subtask_done_date = None
		self.subtask_pause_date = None
		self.subtask_close_date = None
	 	
	def _handle_status(self):
		prev = self.get_doc_before_save()
		if not prev:
			# if self.status == "Open":
			self._reset_for_new_subtask()
			return

		if prev.status == self.status:
			return

		now = now_datetime()
		from_parent = bool(self.flags.get('from_parent_propagation'))

		if from_parent and prev.status in ("Open", "Cancel"):
			self.subtask_start_date = now
			self.last_in_progress_timestamp = now
			if self.status == "Done":
				self.subtask_done_date = now
			self.total_time = 0
			return
		
		if self.status == "Open":
			self._reset_for_new_subtask()

		elif self.status == "In Progress":
			self.subtask_start_date = now
			self.last_in_progress_timestamp = now

		elif self.status in ("Pause", "Done", "Resolved"):
			if not self.last_in_progress_timestamp:
				if prev.status == "Close":
					return
				if prev.status == 'Resolved':
					return
				frappe.throw(f"Can't change status to '{self.status}', change to 'In Progress' first.")
			duration = int((now - get_datetime(self.last_in_progress_timestamp)).total_seconds() / 60)
			self.total_time = (self.total_time or 0) + duration
			self.last_in_progress_timestamp = None
			if self.status == "Done":
				self.subtask_done_date = now
			elif self.status == 'Resolved':
				self.subtask_resolved_date = now
			elif self.status == 'Pause':
				self.subtask_pause_date = now

		elif self.status == "Close":
			self.subtask_close_date = now	

def update_fields(doc, method):
	# if frappe.flags.in_update:
	# 	# frappe.msgprint(f"In update SubTask")
	# 	return
	frappe.flags.in_update = True

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
	print(f"has permission subtask for user: {user}, ptype: {ptype}, doc: {doc.name}")

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

	employee = frappe.get_doc("Employee", employee_id)
	tasks = frappe.get_doc("Tasks", doc.tasks)
	maintask = frappe.get_doc("MainTask", doc.maintask)
	
	parent_task_pic = frappe.get_all(
		"Task PIC",
		filters={"employee": employee_id},
		pluck="parent"
	)
 
	is_owner = doc.owner == user
	is_pic_subtask = doc.pic_subtask == employee_id
	is_maintask_owner = maintask.owner == user
	is_tasks_owner = tasks.owner == user
	is_task_pic = doc.tasks in parent_task_pic
	in_team = doc.maintask in parent_mteam
	in_assign_by_list = doc.maintask in parent_assign_by
	
	if ptype in ("read", None) and (in_team or in_assign_by_list):
		return True

	if ptype == "delete":
		if doc.status in ("Done", "Close", "In Progress", "Pause"):
			frappe.throw(_(f"Sorry {employee.employee_name} you can't delete {doc.subtask_name} subtask because it's already progressing.",
							frappe.PermissionError))
			return False
		maintask = frappe.get_doc("MainTask", doc.maintask)
		if doc.pic_subtask == employee_id and not (is_task_pic or is_owner):
			frappe.throw(f"{employee.employee_name} is pic subtask only and not allowed to deleting {doc.subtask_name} subtask.",
							frappe.PermissionError)
			return False
		check_evaluated = frappe.get_value("Evaluation", {"subtask": doc.name}, "subtask")
		if check_evaluated:
			frappe.throw(_(f"Sorry {employee.employee_name} {doc.subtask_name} subtask is evaluated, you can't delete it.",
							frappe.PermissionError))
			return False
		if is_task_pic and is_owner:
			return True
	elif ptype == "write":
		if is_task_pic or is_maintask_owner or is_owner or is_pic_subtask or in_assign_by_list or is_tasks_owner:
			return True
		else:
			frappe.throw(f"{employee.employee_name} is not allowed to editing {doc.subtask_name} subtask, because not part of maintask or tasks.",
							frappe.PermissionError)
			return False
	elif ptype == "create":
		if is_task_pic or is_maintask_owner:
			return True
		else:
			frappe.throw(f"{employee.employee_name} is not allowed to create {doc.subtask_name} subtask, because not pic task or pic maintask.",
							frappe.PermissionError)
			return False

	if is_owner or is_maintask_owner or is_tasks_owner:
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
	privileges = list()
	if frappe.session.user == "Administrator":
		return privileges.append("admin")

	doc = frappe.get_doc("SubTask", subtask_name)
	employee_id = frappe.get_value("Employee", {"user_id": frappe.session.user}, "name")
	user_roles = frappe.get_all(
		"Has Role", filters={"parent": frappe.session.user}, pluck="role"
	)

	if not employee_id:
		return "none"


	if doc.tasks and doc.maintask:
		tasks = frappe.get_doc("Tasks", doc.tasks)
		owner_task = tasks.owner

		parent_task_pic = frappe.get_all(
			"Task PIC", filters={"employee": employee_id}, pluck="parent"
		)

		parent_assign_by = frappe.get_all(
			"MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
		)
		
		# If this user is in the maintask's "assign_by" list, determine
		# whether they should get a special privilege that controls
		# who may edit `total_time` on the SubTask form. We return
		# one of these markers (when applicable):
		#  - assign_by_maintask                (employee-only PIC -> leader/supervisor/manager allowed)
		#  - assign_by_maintask_supervisor     (PIC is Leader -> only supervisor/manager allowed)
		#  - assign_by_maintask_manager       (PIC is Supervisor -> only manager allowed)
		if doc.maintask in parent_assign_by:
			pic_subtask_user = frappe.get_value("Employee", {"name": doc.pic_subtask}, "user_id")
			pic_subtask_roles = [r.lower() for r in (frappe.get_all("Has Role", filters={"parent": pic_subtask_user}, pluck="role") or [])]
			user_roles_l = [r.lower() for r in (user_roles or [])]
			# PIC has manager role -> conservative: don't expose editing flag here
			if 'manager' in pic_subtask_roles:
				# no extra privilege (only higher authority / admin should edit)
				pass
			# PIC is supervisor -> allow only manager to edit
			elif 'supervisor' in pic_subtask_roles:
				if 'manager' in user_roles_l:
					privileges.append("assign_by_maintask_manager")
			# PIC is leader -> allow supervisor or manager to edit
			elif 'leader' in pic_subtask_roles:
				if 'manager' in user_roles_l or 'supervisor' in user_roles_l:
					privileges.append("assign_by_maintask_supervisor")
			# PIC is regular employee (no leader/supervisor/manager) -> allow
			# leader/supervisor/manager to edit
			else:
				if any(r in user_roles_l for r in ('manager', 'supervisor', 'leader')):
					privileges.append("assign_by_maintask")
				

		if doc.owner == frappe.session.user:
			privileges.append("owner_subtask")

		if tasks.name in parent_task_pic:
			privileges.append("task_pics")

		if owner_task == frappe.session.user:
			privileges.append("owner_task")

		if doc.pic_subtask == employee_id:
			privileges.append("pic_subtask")
   
	print(f"privileges: {privileges}")
	return privileges if privileges else ["none"]


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
		conditions = "WHERE (tp.employee = %(employee_id)s) AND (t.status = 'Open' OR t.status = 'In Progress') AND (t.name LIKE %(txt)s OR t.task_name LIKE %(txt)s)"

	tasks = frappe.db.sql(f"""
		SELECT t.name, t.task_name
		FROM `tabTasks` t
		JOIN `tabTask PIC` tp ON tp.parent = t.name
		{conditions}
		GROUP BY t.name
		ORDER BY t.creation DESC, t.name
		LIMIT %(page_len)s OFFSET %(start)s
	""", {
		"user_id": user,
		"employee_id": employee_id,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
	})
	return tasks

@frappe.whitelist()
def get_task_with_same_pic_and_maintask(doctype, txt, searchfield, start, page_len, filters):
	user = frappe.session.user
	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
	if not filters.get("maintask"):
		return []
	conditions = ""
	if user != "Administrator":
		conditions = "WHERE (tp.employee = %(employee_id)s) AND (t.status = 'Open' OR t.status = 'In Progress') AND (t.name LIKE %(txt)s OR t.task_name LIKE %(txt)s) AND (t.maintask = %(maintask)s)"

	tasks = frappe.db.sql(f"""
		SELECT t.name, t.task_name
		FROM `tabTasks` t
		JOIN `tabTask PIC` tp ON tp.parent = t.name
		{conditions}
		GROUP BY t.name
		ORDER BY t.creation DESC, t.name
		LIMIT %(page_len)s OFFSET %(start)s
	""", {
		"user_id": user,
		"employee_id": employee_id,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len,
		"maintask": filters.get("maintask")
	})
	return tasks

@frappe.whitelist()
def button_evaluation_subtask(subtask):
	user = frappe.session.user
	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
	subtask = frappe.get_doc("SubTask", subtask)
	evaluation_subtask = frappe.get_value("Evaluation", {"subtask": subtask.name}, "name")
	tasks = frappe.get_doc("Tasks", subtask.tasks)
	maintask = frappe.get_doc("MainTask", subtask.maintask)
	roles = frappe.get_all("Has Role", filters={"parent": user}, pluck="role")
	parent_task_pic = frappe.get_all(
			"Task PIC",
			filters={"employee": employee_id},
			pluck="parent"
		)
	parent_assign_by = frappe.get_all(
			"MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
		)
	is_pic = subtask.tasks in parent_task_pic
	print(f"User: {user}, Maintask Owner: {maintask.owner}, is PIC? {is_pic}, Roles: {roles}")
 
	if maintask.owner == user and subtask.status == "Done":
		return "maintask_owner_done"
	if maintask.name in parent_assign_by and subtask.status == "Done" and ('Leader' in roles or 'Manager' in roles or 'Supervisor' in roles):
		return "assign_by_maintask_done"
	# if tasks.owner == user and subtask.status == "Done" and ('Leader' in roles or 'Manager' in roles or 'Supervisor' in roles):
	# 	return "task_owner_done"
	# if subtask.owner == user and subtask.status == "Done" and ('Leader' in roles or 'Manager' in roles or 'Supervisor' in roles):
	# 	return "subtask_owner_done"
	if subtask.tasks in parent_task_pic and ('Leader' in roles or 'Manager' in roles or 'Supervisor' in roles) and subtask.status == "Done":
		return "pic_task_done"
	if user == 'Administrator' and subtask.status == "Done":
		print("Administrator and subtask done")
		return "administrator_done"
	if subtask.status == "Close" and evaluation_subtask:
		print(f"Subtask {subtask.name} already evaluated")
		return {
			"status": "Close",
			"evaluation_name": evaluation_subtask
		}

	return False

@frappe.whitelist()  
def subtask_value_agent_suggestion(title, description):
	try:
		url = "http://192.168.20.239:3019/skillset-classify"
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
		url = "http://192.168.20.239:3019/person-classify"
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

@frappe.whitelist()
def get_issues_by_maintask(doctype, txt, searchfield, start, page_len, filters):
    maintask = filters.get("maintask")
    if not maintask:
        return []

    txt = txt or ""
    issues = frappe.db.sql("""
							  SELECT i.name, i.issue
							  FROM `tabFusion Issue Types` i
							  WHERE i.maintask = %(maintask)s
								AND (i.name LIKE %(txt)s OR i.issue LIKE %(txt)s)
							  GROUP BY i.name
							  ORDER BY i.issue
								  LIMIT %(page_len)s
							  OFFSET %(start)s
							  """, {
		"maintask": maintask,
		"txt": f"%{txt}%",
		"start": start,
		"page_len": page_len
	})
    return [(issue[0], issue[1]) for issue in issues]