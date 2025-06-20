import frappe
from frappe.query_builder.functions import Count


@frappe.whitelist()
def get_evaluation_data():
    data = []

    user = frappe.session.user
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = ""
    if user != "Administrator":
        conditions = "WHERE (mt.owner = %(user)s OR mt.assigned_by = %(employee_id)s OR mt.name IN (SELECT mt2.name FROM `tabMainTask` mt2 LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent WHERE mt2.owner = %(user)s OR %(employee_id)s   OR mteam2.employee = %(employee_id)s)) AND st.status = 'Done'"
        # conditions = "WHERE mt.owner = %(user)s AND st.status = %(status)s"

    query = f"""
                SELECT
                mt.name AS mt_name,
                    mt.maintask_name AS maintask_name,
                    mt.assigned_by_name AS assigned_by,
                    mt.assign_date,
                    mt.due_date,
                    mt.status AS mt_status,
                    t.name AS t_name,
                    t.task_name AS task,
                    t.pic_task_name,
                    st.subtask_name AS sub_task,
                    st.pic_subtask_name,
                    st.target_time AS subtask_target_time,
                    st.value AS value_subtask,
                    ev.performance AS performance,
                    ev.final_target_time AS final_target_time,
                    ev.contribution AS contribution
                FROM `tabMainTask` mt
                LEFT JOIN `tabMainTask Team` mteam ON mt.name = mteam.parent
                LEFT JOIN `tabTasks` t ON t.maintask = mt.name
                LEFT JOIN `tabSubTask` st ON st.tasks = t.name
                LEFT JOIN `tabEvaluation` ev ON ev.subtask = st.name
                {conditions}
                GROUP BY mt.name, t.name, st.name
                ORDER BY mt.name, t.name, st.name
            """

    data = frappe.db.sql(query, {
        "user": user,
        "employee_id": employee_id,
        # "status": filters.get("status")
    },
                         as_dict=True)

    print(f"table data \n{data}")

    return data
