# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow, get_transitions, get_workflow_name
from frappe.core.doctype.version.version import get_diff


class LeaveRequest(Document):
	def validate(self):
		self.prevent_edits_when_final_rejected()
		self.validate_replacement_security()
		self.validate_manager_phase()
		self.validate_hr_phase()

	def on_update(self):
		self.auto_resubmit_after_revise()

	def on_cancel(self):
		self.set_workflow_state_after_cancel()

	def set_workflow_state_after_cancel(self):
		"""If an active workflow defines a docstatus=2 state (e.g. 'Cancelled'),
		set the workflow state field accordingly.

		This avoids cancelled documents staying in their last submitted state (e.g. 'Approve HR'),
		which can make the form appear workflow read-only and hide the Amend action in the UI.
		"""
		if self.docstatus != 2:
			return

		workflow_name = get_workflow_name(self.doctype)
		if not workflow_name:
			return

		state_field = frappe.db.get_value("Workflow", workflow_name, "workflow_state_field") or "workflow_state"
		cancelled_state = frappe.db.get_value(
			"Workflow Document State",
			{"parent": workflow_name, "doc_status": 2, "state": "Cancelled"},
			"state",
		)
		if not cancelled_state:
			return

		if self.get(state_field) == cancelled_state:
			return

		# Use db_set to avoid triggering another full save cycle.
		self.db_set(state_field, cancelled_state, update_modified=False)

	def before_save(self):	
		self.set_fields()		
		self.update_replacement_decision()
	
	def has_permission(self, permtype):
		if permtype == "amend":
			current_user = frappe.session.user
			# Keep System Manager and Administrator unblocked.
			if current_user == "Administrator" or "System Manager" in frappe.get_roles(current_user):
				return True

			# Amend is only allowed for cancelled documents.
			if self.docstatus != 2:
				frappe.throw("You can only amend a cancelled Leave Request.")
				return False

			# Allow the creator/owner to amend their own document.
			if self.owner and self.owner == current_user:
				return True

			frappe.throw("You do not have permission to amend this Leave Request.")
			return False

		if permtype == "create":
			if self.employee:
				employee_user_id = frappe.db.get_value("Employee", self.employee, "user_id")
				if employee_user_id and employee_user_id != frappe.session.user:
					frappe.throw("You can only create a Leave Request for yourself.")
					return False
				else:
					return True
			else:
				frappe.throw("Employee must be set to create a Leave Request.")
				return False
		if permtype == "read":
			return self._has_read_permission()
		if permtype == "write":
			# Mirror front-end restrictions from leave_request.js.
			# - Rejected Manager / Rejected HR: read-only (no further writes)
			# - Pending HR: only HR can write; only HR fields should change
			# - Pending Manager: only Division Leave Approver can write; only Manager fields should change
			# - Pending Replacement / Rejected Replacement: only replacement table should change;
			#   only owner can add rows; replacement employee can only edit own row status/reason
			return self._has_write_permission()
		if permtype == "delete":
			if self.workflow_state not in ["Draft", "Rejected Manager", "Rejected HR", "Rejected Replacement"]:
				frappe.throw("You cannot delete this document as it is not in Draft or Rejected state.")
				return False
			else:
				return True
				
		if permtype == "submit":
			if self.workflow_state != "Approve HR":
				frappe.throw("You can only submit a Leave Request in Approve HR.")
				return False
			else:
				if frappe.session.user == "Administrator" or "Leave Approver" in frappe.get_roles(frappe.session.user):
					return True
				frappe.throw("You do not have permission to submit this Leave Request.")
				return False
			
		if permtype == "cancel":
			if "Leave Approver" in frappe.get_roles(frappe.session.user) or "HR User" in frappe.get_roles(frappe.session.user) or "HR Manager" in frappe.get_roles(frappe.session.user) or "System Manager" in frappe.get_roles(frappe.session.user):
				return True
			frappe.throw("You do not have permission to cancel this Leave Request.")
			return False

	def _has_read_permission(self) -> bool:
		"""Mirror `permission_query_conditions()` rules for single-doc read checks."""
		user = frappe.session.user
		if not user or user == "Administrator":
			return True

		roles = set(frappe.get_roles(user) or [])
		if {"System Manager", "HR User", "HR Manager"} & roles:
			return True

		user_employee = frappe.db.get_value(
			"Employee",
			{"user_id": user},
			["name", "section", "division"],
			as_dict=True,
		)
		if not user_employee or not user_employee.name:
			frappe.throw("User is not linked to an Employee record. Cannot determine permissions.")
			return False

		# Always allow: self as employee OR as replacement.
		if self.employee and self.employee == user_employee.name:
			return True

		for rep in (self.get("employees_replacement") or []):
			if getattr(rep, "employee", None) == user_employee.name:
				return True

		# Leader/Supervisor: same section (by Department.department_name)
		if roles & {"Leader", "Supervisor"} and user_employee.section and self.employee:
			user_section_name = frappe.db.get_value("Department", user_employee.section, "department_name")
			if user_section_name:
				employee_section = frappe.db.get_value("Employee", self.employee, "section")
				if employee_section:
					employee_section_name = frappe.db.get_value(
						"Department", employee_section, "department_name"
					)
					if employee_section_name and employee_section_name == user_section_name:
						return True

		# Manager: same division (by Department.department_name)
		if roles & {"Manager"} and user_employee.division and self.employee:
			user_division_name = frappe.db.get_value("Department", user_employee.division, "department_name")
			if user_division_name:
				employee_division = frappe.db.get_value("Employee", self.employee, "division")
				if employee_division:
					employee_division_name = frappe.db.get_value(
						"Department", employee_division, "department_name"
					)
					if employee_division_name and employee_division_name == user_division_name:
						return True
					
		frappe.throw("You do not have permission to view this Leave Request.")
		return False

	def _has_write_permission(self) -> bool:
		
		current_user = frappe.session.user
		# Keep System Manager and Administrator unblocked.
		if current_user == "Administrator" or "System Manager" in frappe.get_roles(current_user):
			return True

		# New documents: allow writes (field-level restrictions are handled by client).
		if self.is_new():
			return True

		state = self.workflow_state
		final_rejected_states = {"Rejected Manager", "Rejected HR"}

		# Always-allowed top-level changes (system-managed / workflow plumbing)
		always_allowed_fields = {
			"workflow_state",
			"docstatus",
			"modified",
			"modified_by",
			"employee_name",
			"replacements_final_decision",
			"final_status",
		}

		before = getattr(self, "_doc_before_save", None) or self.get_doc_before_save()
		# If we can't diff (e.g. just opening the form), still enforce coarse gating
		# that mirrors the front-end read-only behavior.
		if not before:
			# If this request is coming from Workflow action API, do not apply coarse
			# state-based edit gating here. Workflow engine will validate transitions.
			if self._is_workflow_action_request():
				
				return True

			if state in final_rejected_states:
				frappe.throw("This Leave Request is already rejected and cannot be modified.")
				return False
			if state == "Pending HR":
				is_hr = self._is_current_user_hr_department()
				if not is_hr:
					frappe.throw("Only HR department can edit this Leave Request in Pending HR state.")
					return False
				return True
			if state == "Pending Manager":
				is_approver = self._is_current_user_division_leave_approver()
				if is_approver:
					return True
				frappe.throw("Only the Division Leave Approver can edit this Leave Request in Pending Manager state.")
				return False
			if state in {"Pending Replacement", "Rejected Replacement"}:
				is_owner = (self.owner == current_user) if self.owner else False
				if is_owner:
					return True
				current_employee = frappe.db.get_value("Employee", {"user_id": current_user}, "name")
				if current_employee and any(
					(getattr(r, "employee", None) == current_employee)
					for r in (self.get("employees_replacement") or [])
				):
					return True
				frappe.throw("You do not have permission to edit this Leave Request in Replacement state.")
				return False
			return True

		# If this is a workflow transition (workflow_state changed), do not enforce
		# in-state edit restrictions. This prevents blocking transitions like
		# Pending Manager -> Pending HR done by a non-HR user.
		if before.workflow_state and self.workflow_state != before.workflow_state:
			# Never allow writes after a final rejection.
			if before.workflow_state in final_rejected_states:
				frappe.throw("This Leave Request is already rejected and cannot be modified.")
				return False

			# Transition INTO a final rejected state: allow only workflow/system changes.
			if self.workflow_state in final_rejected_states:
				diff = get_diff(before, self) or {}
				changed_top_level_fields = {
					c[0]
					for c in (diff.get("changed") or [])
					if c and len(c) >= 1 and c[0] and c[0] not in always_allowed_fields
				}
				child_touched = self._get_child_tables_touched_from_diff(diff)
				return not changed_top_level_fields and not child_touched

			return True

		# If already finally rejected, block all further writes.
		# Note: we still allow workflow transitions INTO a rejected state.
		if before.workflow_state in final_rejected_states and self.workflow_state in final_rejected_states:
			frappe.throw("This Leave Request is already rejected and cannot be modified.")
			return False

		diff = get_diff(before, self) or {}

		changed_top_level_fields = {
			c[0]
			for c in (diff.get("changed") or [])
			if c and len(c) >= 1 and c[0] and c[0] not in always_allowed_fields
		}

		child_touched = self._get_child_tables_touched_from_diff(diff)

		# State-specific enforcement (only for states that are explicitly locked in JS)
		state = self.workflow_state

		if state in {"Rejected Manager", "Rejected HR"}:
			# Allow the transition INTO rejected (before was not rejected). Otherwise deny.
			if before.workflow_state not in final_rejected_states:
				# Transition into rejected should only change workflow-ish fields.
				frappe.throw("Only workflow state changes are allowed when rejecting a Leave Request.")
				return not changed_top_level_fields and not child_touched
			frappe.throw("This Leave Request is already rejected and cannot be modified.")
			return False

		if state == "Pending HR":
			if not self._is_current_user_hr_department():
				frappe.throw("Only HR department can edit this Leave Request in Pending HR state.")
				return False
			allowed = {"hr_decision", "hr_reason"}
			if (changed_top_level_fields - allowed) or child_touched:
				frappe.throw("Only HR Decision and HR Reason can be edited in Pending HR state.")
				return False
			return True

		if state == "Pending Manager":
			if not self._is_current_user_division_leave_approver():
				frappe.throw("Only the Division Leave Approver can edit this Leave Request in Pending Manager state.")
				return False
			allowed = {"manager_decision", "manager_reason"}
			if (changed_top_level_fields - allowed) or child_touched:
				frappe.throw("Only Manager Decision and Manager Reason can be edited in Pending Manager state.")
				return False
			return True

		if state in {"Pending Replacement", "Rejected Replacement"}:
			# Only replacement table edits are allowed (matches JS).
			allowed_child_tables = {"employees_replacement"}
			if child_touched - allowed_child_tables:
				frappe.throw("Only changes to the Replacement Employees table are allowed in this state.")
				return False

			# Disallow editing other top-level fields in these states.
			if changed_top_level_fields:
				frappe.throw("Only changes to the Replacement Employees table are allowed in this state.")
				return False

			# Additional rules that exist in JS:
			# - Only owner can add replacement rows on existing docs
			# - Replacement employee can only edit their own row status/reason
			if not self._validate_replacement_table_write_rules(before, diff):
				frappe.throw("You do not have permission to make the attempted changes to the Replacement Employees table.")
				return False

			return True

		# Other states: keep existing behavior (no extra restriction).
		return True

	def _is_workflow_action_request(self) -> bool:
		"""Return True if current request is triggered via Workflow APIs.

		Used to avoid blocking legitimate workflow transitions when doc before-save
		snapshot isn't available in this permission check context.
		"""
		try:
			form_dict = getattr(frappe.local, "form_dict", None) or {}
			cmd = (form_dict.get("cmd") or "").strip()
		except Exception:
			cmd = ""

		return cmd in {
			"frappe.model.workflow.apply_workflow",
			"frappe.model.workflow.bulk_workflow_approval",
		}
	
	def _is_current_user_hr_department(self) -> bool:
		current_user = frappe.session.user
		hr_employee = frappe.db.get_value(
			"Employee",
			{"user_id": current_user},
			["department"],
			as_dict=True,
		)
		if not hr_employee:
			frappe.throw("User is not linked to an Employee record. Cannot determine HR department membership.")
			return False
		return hr_employee.department == "Human Resources"

	def _is_current_user_division_leave_approver(self) -> bool:
		# Same rule as validate_manager_phase
		current_user = frappe.session.user
		division = frappe.db.get_value("Employee", self.employee, "division")
		if not division:
			department = frappe.db.get_value("Employee", self.employee, "department")
			division = department if department else None
			if not division:
				frappe.throw("Employee division/department is not set. Cannot determine Manager approver.")
				return False
		approvers = set(get_division_leave_approvers(division))
		return current_user in approvers

	def _get_child_tables_touched_from_diff(self, diff: dict) -> set[str]:
		child_touched: set[str] = set()
		for key in ("added", "removed", "row_changed"):
			for entry in (diff.get(key) or []):
				# Typical get_diff format: [table_fieldname, ...]
				if isinstance(entry, (list, tuple)) and entry:
					table_field = entry[0]
					if isinstance(table_field, str) and table_field:
						child_touched.add(table_field)
		return child_touched

	def _validate_replacement_table_write_rules(self, before, diff: dict) -> bool:
		"""Server-side mirror of JS restrictions for employees_replacement edits."""
		current_user = frappe.session.user
		is_owner = (self.owner == current_user) if self.owner else False

		# If replacements table is untouched, nothing to validate here.
		child_touched = self._get_child_tables_touched_from_diff(diff)
		if "employees_replacement" not in child_touched:
			return True

		# Only owner can add new replacement rows (existing doc).
		for entry in (diff.get("added") or []):
			if (
				isinstance(entry, (list, tuple))
				and entry
				and entry[0] == "employees_replacement"
				and not is_owner
			):
				return False

		# Determine current employee (for per-row restrictions on status/reason).
		current_employee = frappe.db.get_value("Employee", {"user_id": current_user}, "name")

		# Build lookup for row employee by rowname.
		row_employee_by_name = {
			row.name: row.employee
			for row in (self.get("employees_replacement") or [])
			if getattr(row, "name", None)
		}

		for entry in (diff.get("row_changed") or []):
			if not (isinstance(entry, (list, tuple)) and len(entry) >= 3):
				continue
			if entry[0] != "employees_replacement":
				continue
			rowname = entry[1]
			changes = entry[2] or []
			row_employee = row_employee_by_name.get(rowname)

			for ch in changes:
				if not (isinstance(ch, (list, tuple)) and ch):
					continue
				fieldname = ch[0]

				# JS locks status/reason to the replacement employee only (even for owner).
				if fieldname in {"status", "reason", "decision_by", "decision_date"}:
					# If we can't map current employee, fail open here and rely on validate_* security.
					if not current_employee:
						continue
					if not row_employee or row_employee != current_employee:
						return False
					continue

				# Any other field edits in the child row (e.g. changing the employee link)
				# are treated as owner-only.
				if not is_owner:
					return False

		# If rows were removed by non-owner, deny.
		for entry in (diff.get("removed") or []):
			if (
				isinstance(entry, (list, tuple))
				and entry
				and entry[0] == "employees_replacement"
				and not is_owner
			):
				return False

		return True

	def prevent_edits_when_final_rejected(self):
		"""Reject any edits once the doc is already finally rejected.

		Allows `workflow_state` to differ (ignored), but blocks all other changes,
		including child table edits.
		"""
		if self.is_new():
			return

		before = self.get_doc_before_save()
		if not before:
			return

		final_rejected_states = {"Rejected Manager", "Rejected HR"}
		if before.workflow_state not in final_rejected_states:
			return

		# If transitioning out (unlikely), don't block here.
		if self.workflow_state != before.workflow_state:
			return

		diff = get_diff(before, self)
		if not diff:
			return

		changed = [c for c in (diff.get("changed") or []) if c and c[0] != "workflow_state"]
		if changed or (diff.get("added") or []) or (diff.get("removed") or []) or (diff.get("row_changed") or []):
			changed_fields = [c[0] for c in changed]
			if (diff.get("added") or []) or (diff.get("removed") or []) or (diff.get("row_changed") or []):
				changed_fields.append("child_table")
			frappe.throw(
				"This Leave Request is already rejected and cannot be modified. "
				f"Changed: {', '.join(sorted(set(changed_fields)))}"
			)

	def auto_resubmit_after_revise(self):
		# If a document was previously revised to Rejected Replacement,
		# auto-trigger Resubmit on next save after replacements are fixed.
		# Use frappe.flags to avoid recursion when apply_workflow saves again.
		flag_key = f"leave_request_auto_resubmit::{self.doctype}::{self.name}"
		if frappe.flags.get(flag_key):
			return

		if not self.name or self.is_new():
			return

		if self.workflow_state != "Rejected Replacement":
			return

		# Only resubmit if replacements are no longer rejected (i.e. fixed)
		if self.replacements_final_decision == "Rejected":
			return

		# Must have at least one replacement row (matches workflow condition)
		if not self.get("employees_replacement"):
			return

		if not self._was_previously_revised_from_pending_replacement():
			return

		# Only auto-apply if the action is actually available for this user
		try:
			transitions = get_transitions(self)
		except Exception:
			return

		if not any(t.get("action") == "Resubmit" for t in transitions):
			return

		frappe.flags[flag_key] = True
		try:
			apply_workflow({"doctype": self.doctype, "name": self.name}, "Resubmit")
		except Exception:
			# Don't block save if workflow can't be applied (e.g. missing role/self approval).
			return

	def _was_previously_revised_from_pending_replacement(self) -> bool:
		# Prefer Version history over workflow comments.
		# Notes:
		# - New docs may have workflow_state auto-set to the first workflow state without any workflow comment.
		# - Version will capture workflow_state changes when track_changes is enabled.
		versions = frappe.get_all(
			"Version",
			filters={"ref_doctype": self.doctype, "docname": self.name},
			fields=["data"],
			order_by="creation desc",
			limit=50,
		)

		for v in versions:
			data = frappe.parse_json(v.data) if isinstance(v.data, str) else (v.data or {})
			for change in (data.get("changed") or []):
				if (
					len(change) >= 3
					and change[0] == "workflow_state"
					and change[1] == "Pending Replacement"
					and change[2] == "Rejected Replacement"
				):
					return True

		return False
	
	def set_fields(self):
		self.employee_name = frappe.get_value("Employee", self.employee, "employee_name")
		
	def update_replacement_decision(self):
		if not self.employees_replacement:
			self.replacements_final_decision = "Pending"
			return

		statuses = [row.status for row in self.employees_replacement]

		if "Rejected" in statuses:
			self.replacements_final_decision = "Rejected"
		elif all(s == "Approved" for s in statuses):
			self.replacements_final_decision = "Approved"
		else:
			self.replacements_final_decision = "Pending"

	def validate_replacement_security(self):
		current_user = frappe.session.user
		current_employee = frappe.get_value(
			"Employee", {"user_id": current_user}, ["name", "employee_name"], as_dict=True
		)

		before = self.get_doc_before_save()
		old_status_by_row_name = {}
		if before and getattr(before, "employees_replacement", None):
			old_status_by_row_name = {d.name: d.status for d in before.employees_replacement if d.name}

		for row in self.employees_replacement:
			old_status = old_status_by_row_name.get(row.name)
			status_changed = old_status is not None and row.status != old_status

			# detect perubahan status (khusus approve/reject)
			if status_changed and row.status in ["Approved", "Rejected"]:
				user_id = frappe.db.get_value("Employee", row.employee, "user_id")
				# hanya user terkait yang boleh ubah
				if user_id != current_user:
					employee_name = (current_employee or {}).get("employee_name") or current_user
					frappe.throw(
						f"You ({employee_name}) are not allowed to {row.status} {row.employee_name} status replacement."
					)

				row.decision_by = current_user
				row.decision_date = now()

	def validate_manager_phase(self):
		# Only allow Division leave approver to change manager decision/reason.
		# Division is stored on Employee as a Link to Department.
		current_user = frappe.session.user
		if current_user == "Administrator" or "System Manager" in frappe.get_roles(current_user):
			return

		before = self.get_doc_before_save()
		decision_changed = self.has_value_changed("manager_decision")
		reason_changed = self.has_value_changed("manager_reason")

		# Only enforce when trying to approve/reject or editing the manager reason.
		if self.manager_decision not in ["Approved", "Rejected"]:
			return

		if decision_changed:
			division = frappe.db.get_value("Employee", self.employee, "division")
			if not division:
				department = frappe.db.get_value("Employee", self.employee, "department")
				division = department if department else None
				if not division:
					frappe.throw("Employee division/department is not set. Cannot determine Manager approver.")
					return False

			approvers = get_division_leave_approvers(division)

			if not approvers or current_user not in set(approvers):
				frappe.throw(
					"Only the Division Leave Approver is allowed to set Manager Decision / Reason for this Leave Request."
				)
			
			if self.manager_decision == "Rejected" and not self.manager_reason:
				frappe.throw("Manager Reason is required when rejecting a Leave Request.")
				return False

		if self.manager_decision == "Rejected" and self.workflow_state == "Rejected Manager":
			self.final_status = "Rejected"

    
	def validate_hr_phase(self):
		before = self.get_doc_before_save()
		decision_changed = self.has_value_changed("hr_decision")
		reason_changed = self.has_value_changed("hr_reason")

		# Only enforce when trying to approve/reject or editing the hr reason.
		if self.hr_decision not in ["Approved", "Rejected"]:
			return

		if decision_changed:
			current_user = frappe.session.user

			hr_employee = frappe.db.get_value(
				"Employee",
				{"user_id": current_user},
				["department", "company"],
				as_dict=True
			)

			if not hr_employee:
				frappe.throw("Invalid HR user.")

			# cek department HR
			if hr_employee.department != "Human Resources":
				frappe.throw("Only HR department can approve.")

			if self.hr_decision == "Rejected" and not self.hr_reason:
				frappe.throw("HR Reason is required when rejecting a Leave Request.")
				return False

		if self.hr_decision == "Rejected" and self.workflow_state == "Rejected HR":
			self.final_status = "Rejected"

		if self.hr_decision == "Approved" and self.workflow_state == "Approve HR":
			self.final_status = "Approved"


def get_division_leave_approvers(division: str) -> list[str]:
	"""Return list of User IDs configured as leave approvers for a Division (Department).

	Uses ignore_permissions to avoid child-table permission checks failing when legacy/bad
	Department Approver rows exist with invalid parenttype.
	"""
	if not division:
		return []

	return frappe.get_all(
		"Department Approver",
		filters={
			"parent": division,
			"parenttype": "Department",
			"parentfield": "leave_approvers",
		},
		pluck="approver",
		ignore_permissions=True,
	)


@frappe.whitelist()
def is_current_user_division_leave_approver(employee: str) -> bool:
	"""Check if session user is configured as division leave approver for given employee."""
	if not employee:
		return False

	division = frappe.db.get_value("Employee", employee, "division")
	if not division:
		department = frappe.db.get_value("Employee", employee, "department")
		division = department if department else None
		if not division:
			frappe.throw("Employee division/department is not set. Cannot determine Manager approver.")
			return False

	approvers = set(get_division_leave_approvers(division))
	return frappe.session.user in approvers

def permission_query_conditions(user: str, doctype: str | None = None) -> str | None:
	"""Permission Query Condition hook for Leave Request.

	Configured via hooks (see hrms/hooks.py).

	Role rules (per request):
	- HR User / HR Manager / System Manager: can see all
	- Leader / Supervisor: can see docs where employee.section matches theirs (by Department.department_name)
	- Manager: can see docs where employee.division matches theirs (by Department.department_name)
	- Any non-HR user: can always see docs where they're the employee OR in employees_replacement child table
	"""
	if not user or user == "Administrator":
		return None

	roles = set(frappe.get_roles(user) or [])
	if {"System Manager", "HR User", "HR Manager"} & roles:
		return None

	user_employee = frappe.db.get_value(
		"Employee",
		{"user_id": user},
		["name", "section", "division"],
		as_dict=True,
	)
	if not user_employee or not user_employee.name:
		return "1=0"

	conditions: list[str] = []

	# Always allow: self as employee OR as replacement (even if section/division differs)
	ue = frappe.db.escape(user_employee.name)
	conditions.append(
		f"""(
			`tabLeave Request`.employee = {ue}
			OR EXISTS (
				SELECT 1
				FROM `tabEmployee Replacement` rep
				WHERE rep.parent = `tabLeave Request`.name
					AND rep.parenttype = 'Leave Request'
					AND rep.parentfield = 'employees_replacement'
					AND rep.employee = {ue}
			)
		)"""
	)

	leader_roles = {"Leader", "Supervisor"}
	manager_roles = {"Manager"}

	# Leader/Supervisor: same section (by department_name)
	if roles & leader_roles and user_employee.section:
		user_section_name = frappe.db.get_value("Department", user_employee.section, "department_name")
		if user_section_name:
			es = frappe.db.escape(user_section_name)
			conditions.append(
				f"""EXISTS (
					SELECT 1
					FROM `tabEmployee` e_doc
					JOIN `tabDepartment` d_doc ON d_doc.name = e_doc.section
					WHERE e_doc.name = `tabLeave Request`.employee
						AND d_doc.department_name = {es}
				)"""
			)

	# Manager: same division (by department_name)
	if roles & manager_roles and user_employee.division:
		user_division_name = frappe.db.get_value("Department", user_employee.division, "department_name")
		if user_division_name:
			ed = frappe.db.escape(user_division_name)
			conditions.append(
				f"""EXISTS (
					SELECT 1
					FROM `tabEmployee` e_doc
					JOIN `tabDepartment` d_doc ON d_doc.name = e_doc.division
					WHERE e_doc.name = `tabLeave Request`.employee
						AND d_doc.department_name = {ed}
				)"""
			)
			

	return "(" + " OR ".join(conditions) + ")"