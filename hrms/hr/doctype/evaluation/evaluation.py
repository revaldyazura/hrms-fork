# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt
from marshmallow.utils import pluck

import frappe
from frappe import _, scrub, throw
from frappe.model.document import Document


class Evaluation(Document):
    def validate(self):

        self.validate_performance()

    def validate_performance(self):
        if self.performance > 120:
            throw(_("Performance grade cannot be greater than 120."))


def update_fields(doc, method):
    # Prevent infinite loop
    if frappe.flags.in_update:
        frappe.msgprint(f"in update (eval fields)")
        return
    frappe.flags.in_update = True

    # Check if performance and subtask are filled
    if not doc.performance or not doc.subtask:
        frappe.flags.in_update = False
        return

    subtask = frappe.get_doc("SubTask", doc.subtask)
    tasks_doc = frappe.get_doc("Tasks", subtask.tasks)
    # task_name = subtask.tasks
    doc.pic_subtask = subtask.pic_subtask
    doc.tasks = subtask.tasks
    doc.maintask = tasks_doc.maintask
    # doc.final_target_time = (subtask.target_time * doc.performance)/100
    doc.final_target_time = round((subtask.target_time * doc.performance)/100, 2)
    doc.save(ignore_permissions=True)

    frappe.flags.in_update = False

    if subtask.status == 'Open':
        subtask.status = 'Done'
        subtask.save(ignore_permissions=True)
        frappe.msgprint(f"SubTask '{subtask.subtask_name}' status updated to {subtask.status} after the performance is evaluated.")

    # all_subtasks = frappe.get_all('SubTask', filters={'tasks': subtask.tasks}, fields=['name', 'target_time', 'value'])
    # total_subtask = len(all_subtasks)

    all_subtasks = frappe.get_all('SubTask', filters={'maintask': subtask.maintask}, fields=['name', 'target_time', 'value'])
    total_subtask = len(all_subtasks)

    # evaluations = frappe.get_all('Evaluation', filters={'tasks': subtask.tasks}, fields=['name', 'subtask', 'performance'])
    # evaluated_subtasks = len(evaluations)
    evaluations = frappe.get_all('Evaluation', filters={'maintask': tasks_doc.maintask}, fields=['name', 'subtask', 'performance'])
    evaluated_subtasks = len(evaluations)

    if total_subtask == evaluated_subtasks and total_subtask > 0:
        total_tvr = 0
        subtask_map = {s['name']: s for s in all_subtasks}

        eval_tvr_map = {}

        for eval in evaluations:
            sub = subtask_map.get(eval['subtask'])
            if sub:
                eval_tvr = (sub['target_time'] * int(sub['value']) * eval['performance']) / 100
                eval_tvr_map[eval['name']] = eval_tvr
                total_tvr += eval_tvr

        if total_tvr > 0:
            for eval in evaluations:
                eval_doc = frappe.get_doc('Evaluation', eval.name)
                eval_tvr = eval_tvr_map.get(eval['name'], 0)
                # eval_doc.contribution = (eval_tvr / total_tvr) * 100, 2
                eval_doc.contribution = str(round((eval_tvr / total_tvr) * 100, 2)) + "%"
                eval_doc.save(ignore_permissions=True)

    frappe.flags.in_update = False

    # tv = subtask.target_time * subtask.value
    # tvr = (tv * doc.grade)/100
    # doc.contribution = (tvr/all_tvr_in_subtask_with_same_task)*100%

def after_delete(doc, method):
    subtask = frappe.get_doc("SubTask", doc.subtask)
    if subtask.status == 'Done':
        subtask.status = 'Open'
        subtask.save(ignore_permissions=True)
        frappe.msgprint(f"SubTask '{subtask.subtask_name}' status updated to {subtask.status} after deleting evaluation.")

@frappe.whitelist()
def get_subtask_as_owner(doctype, txt, searchfield, start, page_len, filters):
    user_id = frappe.session.user
    # employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    subtasks = frappe.db.sql("""
        SELECT st.name, st.subtask_name
        FROM `tabSubTask` st
        JOIN `tabMainTask` mt ON st.maintask = mt.name
        WHERE st.owner = %(user_id)s OR mt.owner = %(user_id)s
        GROUP BY st.name
    """, {
        "user_id": f"{user_id}"
    })
    return subtasks

def permission_query_conditions(doc, ptype=None, user=None, debug=False):
    user_id = user or frappe.session.user

    print(f'{user_id} is the user')

    roles = frappe.get_all("Has Role", filters={"parent": user_id}, pluck="role")
    print(f'{roles} is user roles')
    if "System Manager" in roles:
        return ""

    employee_id = frappe.get_value("Employee", {"user_id": user_id}, "name")
    print((f'employee id: {employee_id}'))
    if not employee_id:
        return "1=0"

    return  f"""
        (`tabEvaluation`.`pic_subtask` = '{employee_id}'
        OR `tabEvaluation`.`owner` = '{user_id}'
        OR `tabEvaluation`.`maintask` IN (
            SELECT `name` FROM `tabMainTask` WHERE `owner` = '{user_id}' OR `assigned_by` = '{employee_id}'
        )OR `tabEvaluation`.`tasks` IN (
            SELECT `name` FROM `tabTasks` WHERE `owner` = '{user_id}' OR `pic_task` = '{employee_id}'
        ))
    """
