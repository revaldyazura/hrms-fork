import frappe
from frappe.query_builder.functions import Count

#
# @frappe.whitelist()
# def get_main_task_data():
#     data = []
#
#     user = frappe.session.user
#     employee_id = frappe.get_value("Employee", {"user_id": user}, "name")
#
#     conditions = ""
#     if user != "Administrator":
#         conditions = "WHERE mt.owner = %(user)s OR mt.assigned_by = %(employee_id)s OR mt.name IN (SELECT mt2.name FROM `tabMainTask` mt2 LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent WHERE mt2.owner = %(user)s OR %(employee_id)s OR mteam2.employee = %(employee_id)s)"
#
#     query = f"""
#                 SELECT
#                 mt.name AS mt_name,
#                     mt.maintask_name AS maintask_name,
#                     mt.assigned_by_name AS assigned_by,
#                     GROUP_CONCAT(emp.employee_name SEPARATOR ', ') AS team_members,
#                     mt.assign_date,
#                     mt.due_date,
#                     mt.status AS mt_status,
#                     t.name AS t_name,
#                     t.task_name AS task,
#                     t.target_time,
#                     t.pic_task_name,
#                     st.subtask_name AS sub_task,
#                     st.pic_subtask_name,
#                     st.target_time AS subtask_target_time,
#                     st.value AS value_subtask,
#                     st.status AS sub_task_status
#                 FROM `tabMainTask` mt
#                 LEFT JOIN `tabMainTask Team` mteam ON mt.name = mteam.parent
#                 LEFT JOIN `tabEmployee` emp ON mteam.employee = emp.name
#                 LEFT JOIN `tabTasks` t ON t.maintask = mt.name
#                 LEFT JOIN `tabSubTask` st ON st.tasks = t.name
#                 {conditions}
#                 GROUP BY mt.name, t.name, st.name
#                 ORDER BY mt.name, t.name, st.name
#             """
#
#     data = frappe.db.sql(query, {
#         "user": user,
#         "employee_id": employee_id,
#         # "status": filters.get("status")
#     },
#                          as_dict=True)
#
#
#     return data

def get_team_members_map():
    team_data = frappe.db.sql("""
        SELECT
            mteam.parent AS main_task,
            GROUP_CONCAT(emp.employee_name SEPARATOR ', ') AS members
        FROM `tabMainTask Team` mteam
        LEFT JOIN `tabEmployee` emp ON mteam.employee = emp.name
        GROUP BY mteam.parent
    """, as_dict=True)

    return {row["main_task"]: row["members"] for row in team_data}

@frappe.whitelist()
def get_task_report_data():
    user = frappe.session.user
    employee_id = frappe.get_value("Employee", {"user_id": user}, "name")

    conditions = ""
    if user != "Administrator":
        conditions = """
            WHERE
                mt.owner = %(user)s
                OR mt.assigned_by = %(employee_id)s
                OR mt.name IN (
                    SELECT mt2.name
                    FROM `tabMainTask` mt2
                    LEFT JOIN `tabMainTask Team` mteam2 ON mt2.name = mteam2.parent
                    WHERE mt2.owner = %(user)s
                    OR mteam2.employee = %(employee_id)s
                )
        """

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
            t.target_time,
            emp_tp.user_id AS pic_task_user_id,
            emp_tp.employee_name AS task_pic_name,
            st.owner AS sub_task_owner,
            st.subtask_name AS sub_task,
            st.pic_subtask_name,
            st.target_time AS subtask_target_time,
            st.value AS value_subtask,
            st.status AS sub_task_status
        FROM `tabMainTask` mt
        LEFT JOIN `tabTasks` t ON t.maintask = mt.name
        LEFT JOIN `tabTask PIC` tp ON tp.parent = t.name
        LEFT JOIN `tabEmployee` emp_tp ON tp.employee = emp_tp.name
        LEFT JOIN `tabSubTask` st ON st.tasks = t.name
        {conditions}
        ORDER BY mt.name, t.name, tp.employee, st.name
    """

    values = {
        "user": user,
        "employee_id": employee_id
    }

    raw_data = frappe.db.sql(query, values, as_dict=True)

    # Post-process team_members
    team_map = get_team_members_map()

    for row in raw_data:
        row["team_members"] = team_map.get(row["mt_name"], "")

    return raw_data
