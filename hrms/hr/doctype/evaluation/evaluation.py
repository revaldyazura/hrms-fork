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


def on_update(doc, method):
    # Prevent infinite loop
    if frappe.flags.in_update:
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

    print(f'{total_subtask} total subtask with same maintask')
    print(f'{evaluated_subtasks} evaluated subtask with same maintask')

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
                eval_doc.contribution = round((eval_tvr / total_tvr) * 100, 2)
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
