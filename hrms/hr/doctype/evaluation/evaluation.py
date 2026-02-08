# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
from datetime import datetime

from marshmallow.utils import pluck
import frappe
from frappe.utils import get_link_to_form
from frappe import _, scrub, throw
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime


class Evaluation(Document):
	def validate(self):
		print("validate eval called")
		self.validate_performance()
		self.validate_evaluation_data()

	def before_insert(self):
		print("before insert eval called")
		subtask = frappe.get_doc("SubTask", self.subtask)
		if subtask.status == "Done":
			# frappe.db.set_value(
			# 	"SubTask",
			# 	self.subtask,
			# 	{
			# 		"status": "Close",
			# 		"subtask_close_date": frappe.utils.getdate(now_datetime()),
			# 	},
			# )
			subtask.status = "Close"
			subtask.save()
		else:
			frappe.throw(
				f"You cannot create Evaluation for this SubTask because its status is not 'Done'.",
				frappe.ValidationError,
			)

	def validate_performance(self):
		if self.performance > 120:
			throw(_("Performance grade cannot be greater than 120."))

	def validate_evaluation_data(self):
		self.created_by = frappe.db.get_value(
			"Employee", {"user_id": self.owner}, "employee_name"
		)

	def after_insert(self):
		if getattr(frappe.flags, "bulk_evaluation_creation", False):
			return
		print("after insert eval called")
		subtask_route = f"/app/subtask/{self.subtask}"
		eval_route = f"/app/evaluation/{self.name}"
		open_eval_btn = (
			f"<div style='margin-top:12px; display:flex; justify-content:flex-end;'>"
			f"<a class='btn btn-primary' href='{eval_route}' style='min-width:170px; text-align:center;'>Open Evaluation</a>"
			f"</div>"
		)
		open_subtask_btn = (
			f"<div style='margin-top:12px; display:flex; justify-content:flex-end;'>"
			f"<a class='btn btn-primary' href='{subtask_route}' style='min-width:170px; text-align:center;'>Open SubTask</a>"
			f"</div>"
		)
		link_evaluation_html = get_link_to_form(
			"Evaluation", self.name, label=self.name
		)
		subtask_name = frappe.db.get_value("SubTask", self.subtask, "subtask_name")
		link_subtask_html = get_link_to_form(
			"SubTask", self.subtask, label=subtask_name
		)
		# Decide which button to show depending on where the request came from.
		# If creation is initiated from a SubTask page (e.g. via subtask.js), the
		# HTTP Referer will typically contain '/app/subtask/'. In that case, show
		# the 'Open Evaluation' button (open_eval_btn). Otherwise (e.g. user created
		# the Evaluation from the Evaluation doctype/form), show 'Open SubTask'.
		btn_html = open_eval_btn
		try:
			request = getattr(frappe.local, "request", None)
			headers = getattr(request, "headers", None) if request else None
			referer = None
			if headers:
				# WSGI headers mapping; headers may be a dict-like
				referer = headers.get("Referer") or headers.get("referer")
			# Fallback: sometimes frappe.request is available
			if not referer and hasattr(frappe, "request"):
				_r = getattr(frappe, "request")
				if _r and getattr(_r, "headers", None):
					referer = _r.headers.get("Referer") or _r.headers.get("referer")
			if referer and "/app/subtask/" in referer:
				btn_html = open_eval_btn
			else:
				# default to open_subtask_btn when not coming from a subtask page
				btn_html = open_subtask_btn
		except Exception:
			# In any unexpected case, fall back to showing the evaluation button
			btn_html = open_eval_btn

		msg_html = (
			f"SubTask <b>{link_subtask_html}</b> status updated to Close after the performance is evaluated. Evaluation <b>{link_evaluation_html}</b> created from Evaluated SubTask "
			+ btn_html
		)

		frappe.msgprint(msg_html, title="Evaluation Created", indicator="green")


def update_fields(doc, method):

	if frappe.flags.in_update:
		# frappe.msgprint(f"In update Evaluation")
		return
	frappe.flags.in_update = True

	print("update fields evaluation called")

	subtask = frappe.get_doc("SubTask", doc.subtask)

	doc.pic_subtask = subtask.pic_subtask
	doc.tasks = subtask.tasks
	doc.maintask = subtask.maintask
	doc.final_target_time = round(
		(subtask.target_time_minutes * doc.performance) / 100, 2
	)
	doc.save(ignore_permissions=True)

	all_subtasks = frappe.get_all(
		"SubTask",
		filters={"maintask": subtask.maintask},
		fields=["name", "target_time_minutes", "value"],
	)
	total_subtask = len(all_subtasks)

	evaluations = frappe.get_all(
		"Evaluation",
		filters={"maintask": subtask.maintask},
		fields=["name", "subtask", "performance"],
	)
	evaluated_subtasks = len(evaluations)

	if total_subtask == evaluated_subtasks and total_subtask > 0:
		total_tvr = 0
		subtask_map = {s["name"]: s for s in all_subtasks}

		eval_tvr_map = {}

		for eval in evaluations:
			sub = subtask_map.get(eval["subtask"])
			if sub:
				eval_tvr = (
					sub["target_time_minutes"] * int(sub["value"]) * eval["performance"]
				) / 100
				eval_tvr_map[eval["name"]] = eval_tvr
				total_tvr += eval_tvr

		if total_tvr > 0:
			for eval in evaluations:
				eval_tvr = eval_tvr_map.get(eval["name"], 0)
				contribution = str(round((eval_tvr / total_tvr) * 100, 2)) + "%"
				frappe.db.set_value(
					"Evaluation", eval.name, "contribution", contribution
				)

	frappe.flags.in_update = False


def has_permission(doc, ptype, user):
	print(
		"has permission evaluation doc:",
		doc.name,
		"called for user:",
		user,
		"ptype:",
		ptype,
	)

	if frappe.session.user == "Administrator":
		return True

	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
	if not employee_id:
		return False

	roles = frappe.get_all("Has Role", filters={"parent": user}, pluck="role")

	parent_assign_by = frappe.get_all(
		"MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
	)

	parent_mteam = frappe.get_all(
		"MainTask Team", filters={"employee": employee_id}, pluck="parent"
	)

	parent_task_pic = frappe.get_all(
		"Task PIC", filters={"employee": employee_id}, pluck="parent"
	)

	employee = frappe.get_doc("Employee", employee_id)
	tasks = frappe.get_doc("Tasks", doc.tasks)
	maintask = frappe.get_doc("MainTask", doc.maintask)

	# Grant owner access only for existing documents (not during creation)
	# New/unsaved docs typically have __islocal set, and ptype will be "create".
	is_new_doc = doc.is_new()

	if is_new_doc and ptype == "create":
		subtask_status = frappe.get_value("SubTask", doc.subtask, "status")
		print(f"subtask status {subtask_status}")
		if subtask_status != "Done":
			frappe.throw(
				"You cannot create Evaluation for this SubTask because its status is not 'Done'.",
				frappe.PermissionError,
			)

	if doc.owner == user and not is_new_doc:
		print(f"owner access granted to {user}")
		return True

	privileged_roles = {"Leader", "Manager", "Supervisor"}
	has_privileged_role = any(r in privileged_roles for r in roles)
	is_task_owner = tasks.owner == user
	is_maintask_owner = maintask.owner == user
	is_maintask_assign_by = maintask.name in parent_assign_by
	is_task_pic = tasks.name in parent_task_pic

	if ptype in ("create", "write", "delete"):
		if has_privileged_role and (
			is_task_pic or is_maintask_owner or is_maintask_assign_by
		):
			print(
				f"maintask owner {is_maintask_owner}, assign by {is_maintask_assign_by}, task pic {is_task_pic}, roles {roles}"
			)
			return True
		else:
			if ptype == "delete":
				frappe.throw(
					"You cannot delete this Evaluation because you do not meet the required criteria (required role and must be PIC Task, MainTask Owner, Tasks Owner).",
					frappe.PermissionError,
				)
			else:
				frappe.throw(
					f"You cannot {'create' if ptype == 'create' else 'edit'} this Evaluation because you do not meet the required criteria (required role and must be PIC Task, MainTask Owner, Tasks Owner).",
					frappe.PermissionError,
				)

	if ptype in ("read", None) and (
		doc.maintask in parent_mteam or doc.maintask in parent_assign_by
	):
		return True

	frappe.throw(
		f"{employee.employee_name} is not allowed to accessing {doc.subtask_name} evaluation.",
		frappe.PermissionError,
	)
	return False


def after_delete(doc, method):
	subtask = frappe.get_doc("SubTask", doc.subtask)
	if subtask.status == "Close":
		subtask.status = "Done"
		subtask.save()
		subtask_route = f"/app/subtask/{subtask.name}"
		eval_route = f"/app/evaluation/{doc.name}"
		open_eval_btn = (
			f"<div style='margin-top:12px; display:flex; justify-content:flex-end;'>"
			f"<a class='btn btn-primary' href='{eval_route}' style='min-width:170px; text-align:center;'>Open Evaluation</a>"
			f"</div>"
		)
		open_subtask_btn = (
			f"<div style='margin-top:12px; display:flex; justify-content:flex-end;'>"
			f"<a class='btn btn-primary' href='{subtask_route}' style='min-width:170px; text-align:center;'>Open SubTask</a>"
			f"</div>"
		)
		link_evaluation_html = get_link_to_form(
			"Evaluation", subtask.name, label=doc.name
		)
		link_subtask_html = get_link_to_form(
			"SubTask", subtask.name, label=subtask.subtask_name
		)
		msg_html = (
			f"SubTask <b>{link_subtask_html}</b> status revert back to Done after this evaluation <b>{link_evaluation_html}</b> is deleted."
			+ open_subtask_btn
		)

		frappe.msgprint(msg_html, title="Evaluation Deleted", indicator="orange")


@frappe.whitelist()
def user_edit_evaluation(subtask):
	print("user edit evaluation called")
	user = frappe.session.user
	privileges = list()
	if user == "Administrator":
		return ["admin"]

	doc = frappe.get_doc("SubTask", subtask)
	employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
	roles = frappe.get_all("Has Role", filters={"parent": user}, pluck="role")
	print(f"roles: {roles}")
	maintask = frappe.get_doc("MainTask", doc.maintask)

	if not employee_id:
		return False

	if doc.owner == frappe.session.user:
		return "owner_evaluation"

	if doc.tasks:
		tasks = frappe.get_doc("Tasks", doc.tasks)
		# owner_task = tasks.owner

		parent_task_pic = frappe.get_all(
			"Task PIC", filters={"employee": employee_id}, pluck="parent"
		)

		parent_assign_by = frappe.get_all(
			"MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
		)

		# if tasks.name in parent_task_pic and (
		# 	"Leader" in roles or "Manager" in roles or "Supervisor" in roles
		# ):
		# 	privileges.append("task_pics_leader")

		# if owner_task == frappe.session.user:
		# 	privileges.append("owner_task")

		if doc.pic_subtask == employee_id and all(
			r not in roles for r in ("Leader", "Manager", "Supervisor")
		):
			privileges.append("pic_subtask_only")

		# if maintask.name in parent_assign_by and (
		# 	"Leader" in roles or "Manager" in roles or "Supervisor" in roles
		# ):
		# 	privileges.append("assign_by_maintask")

		if maintask.owner == frappe.session.user:
			privileges.append("owner_maintask")
		
		if doc.maintask in parent_assign_by:
			pic_subtask_user = frappe.get_value("Employee", {"name": doc.pic_subtask}, "user_id")
			pic_subtask_roles = [r.lower() for r in (frappe.get_all("Has Role", filters={"parent": pic_subtask_user}, pluck="role") or [])]
			user_roles_l = [r.lower() for r in (roles or [])]
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

		print(f"privileges: {privileges}")
		return privileges if privileges else ["none"]


@frappe.whitelist()
def get_done_subtask_as_evaluator(doctype, txt, searchfield, start, page_len, filters):
	user_id = frappe.session.user

	employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

	subtasks = frappe.db.sql(
		"""
		SELECT st.name, st.subtask_name
		FROM `tabSubTask` st
		JOIN `tabTasks` t ON st.tasks = t.name
		JOIN `tabMainTask` mt ON st.maintask = mt.name
		JOIN `tabMainTask Assign By` mab ON mab.parent = st.maintask
  		JOIN `tabTask PIC` tp ON tp.parent = st.tasks
		WHERE ( mt.owner = %(user_id)s OR tp.employee = %(employee_id)s OR mab.employee = %(employee_id)s) AND st.status = 'Done' AND (st.name LIKE %(txt)s OR st.subtask_name LIKE %(txt)s)
		GROUP BY st.name
		  ORDER BY st.creation DESC, st.name
	""",
		{"user_id": f"{user_id}", "txt": f"%{txt}%", "employee_id": f"{employee_id}"},
	)
	print(f"done subtasks {subtasks}")
	return subtasks


def permission_query_conditions(doc, ptype=None, user=None, debug=False):
	user_id = user or frappe.session.user

	roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")

	if "System Manager" in roles and user_id == "Administrator":
		return ""

	employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")

	parent_mteam = frappe.get_all(
		"MainTask Team", filters={"employee": employee_id}, pluck="parent"
	)

	parent_assign_by = frappe.get_all(
		"MainTask Assign By", filters={"employee": employee_id}, pluck="parent"
	)

	if not employee_id:
		return "1=0"

	maintask_ids = "', '".join(parent_mteam)

	assign_by_maintask_ids = "', '".join(parent_assign_by)

	return f"""
		(`tabEvaluation`.`pic_subtask` = '{employee_id}'
		OR `tabEvaluation`.`owner` = '{user_id}'
		OR `tabEvaluation`.`maintask` IN (
			SELECT `name` FROM `tabMainTask` WHERE `owner` = '{user_id}' OR `name` IN ('{maintask_ids}')
		) OR `tabEvaluation`.`tasks` IN (
			SELECT `name` FROM `tabTasks` WHERE `owner` = '{user_id}'
		)OR `tabEvaluation`.`maintask` IN (SELECT `name` FROM `tabMainTask` WHERE name IN ('{assign_by_maintask_ids}')))
	"""
