import frappe
import xlsxwriter
import dateparser
import hashlib
from io import BytesIO
from datetime import datetime, timedelta
from itertools import groupby

def get_subtask_type_map():
    types_data = frappe.db.sql("""
                              SELECT stype.parent                                   AS subtask,
                                    GROUP_CONCAT(stype.subtask_type SEPARATOR ', ')AS type
                              FROM `tabSubTask Type` stype
                              GROUP BY stype.parent
                              """, as_dict=True)
    
    data = {row["subtask"]: row["type"] for row in types_data}

    return data

def calculate_working_hours(from_date_str, to_date_str, holiday_list_name):
    from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
    to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

    holiday_dates = set(
        frappe.get_all("Holiday", filters={
            "parent": holiday_list_name,
            "holiday_date": ["between", [from_date, to_date]]
        }, pluck="holiday_date")
    )

    total_holiday = len(holiday_dates)
    total_hours = 0
    day = from_date
    while day <= to_date:
        if day not in holiday_dates:
            total_hours += 8
        day += timedelta(days=1)

    return total_hours, total_holiday


def date_change_format(date_source, date_format="%d %B %Y"):
    if isinstance(date_source, str):
        date_obj = dateparser.parse(date_source)
    else:
        date_obj = date_source

    formatted_datetime = date_obj.strftime(date_format)
    return formatted_datetime


@frappe.whitelist()
def export_team_task_management(filters=None):
    filters = frappe.parse_json(filters or '{}')

    query = """SELECT st.pic_subtask_name,
                      st.maintask,
                      st.maintask_name,
                      st.tasks,
                      st.tasks_name AS task_name,
                      st.name AS subtask,
                      st.subtask_name,
                      st.value AS value_subtask,
                      st.target_time_minutes,
                      st.status AS subtask_status,
                      emp.team
               FROM `tabSubTask` st
                        LEFT JOIN `tabEmployee` emp ON emp.name = st.pic_subtask \
            """

    conditions = []
    values = {}
    from_date = None
    to_date = None

    if filters.get("team"):
        conditions.append("team = %(team)s")
        values["team"] = filters["team"]
    if filters.get("from_date") and filters.get("to_date"):
        from_date = filters.get("from_date")
        to_date = filters.get("to_date")
        conditions.append("subtask_open_date BETWEEN %(from_date)s AND %(to_date)s")
        # conditions.append("due_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters["from_date"]
        values["to_date"] = filters["to_date"]

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    data = frappe.db.sql(query, values, as_dict=True)
    for row in data:
        row["subtask_types"] = get_subtask_type_map().get(row["subtask"], "")
    team_filename = data[0].get('team') if data else filters.get('team')

    total_working_hours, total_holiday = calculate_working_hours(from_date, to_date,
                                                                 'Annual Holiday') if to_date and from_date else 0

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Report Team")

    bold_format = workbook.add_format({'bold': True})
    center_format = workbook.add_format({'align': 'center',
                                         'valign': 'vcenter',
                                         'text_wrap': True,
                                         'border': 1})
    base_colors = [
        "#e0f2f1", "#c8e6c9", "#dcedc8"
    ]
    header_format = workbook.add_format({'bold': True, 'align': 'center',
                                         'valign': 'vcenter',
                                         'text_wrap': True,
                                         'border': 1})
    additional_data_format = workbook.add_format({
        'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
        'border': 1, 'bg_color': '#f0f4c3'
    })
    main_task_color_map = {}
    format_cache = {}
    sheet.set_column("A:J", 20)

    headers = ["Team", "Employee", "MainTask", "Task", "SubTask", "SubTask Type", "SubTask Value", "SubTask Target Time (Minutes)", "SubTask Status"]
    for col, h in enumerate(headers):
        sheet.write(0, col, h, header_format)

    start_row = 1
    row = start_row

    data.sort(key=lambda x: (x["team"], x["pic_subtask_name"], x["maintask"], x["tasks"]))

    for team_key, team_rows in groupby(data, key=lambda x: x["team"]):
        team_rows = list(team_rows)
        team_row_start = row
        for emp_key, emp_rows in groupby(team_rows, key=lambda x: x["pic_subtask_name"]):
            emp_rows = list(emp_rows)
            emp_row_start = row
            for mt_key, mt_rows in groupby(emp_rows, key=lambda x: x["maintask"]):
                mt_rows = list(mt_rows)
                mt_row_start = row
                if mt_key not in main_task_color_map:
                    hash_val = int(hashlib.md5(mt_key.encode()).hexdigest(), 16)
                    color = base_colors[hash_val % len(base_colors)]
                    main_task_color_map[mt_key] = color

                bg_color = main_task_color_map[mt_key]
                if bg_color not in format_cache:
                    format_cache[bg_color] = workbook.add_format({
                        'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                        'border': 1, 'bg_color': bg_color
                    })
                colored_format = format_cache[bg_color]

                for t_key, t_rows in groupby(mt_rows, key=lambda x: x["tasks"]):
                    t_rows = list(t_rows)
                    t_row_start = row
                    for tr in t_rows:

                        sheet.write(row, 4, tr["subtask_name"], colored_format)
                        sheet.write(row, 5, tr["subtask_types"], colored_format)
                        sheet.write_number(row, 6, int(tr["value_subtask"]), colored_format)
                        sheet.write_number(row, 7, int(tr["target_time_minutes"]), colored_format)
                        sheet.write(row, 8, tr["subtask_status"], colored_format)
                        row += 1

                    # Merge Task
                    if row - t_row_start > 1:
                        sheet.merge_range(t_row_start, 3, row - 1, 3, t_rows[0].get("task_name", t_key), colored_format)
                    else:
                        sheet.write(t_row_start, 3, t_rows[0].get("task_name", t_key), colored_format)
                # Merge Main Task
                if row - mt_row_start > 1:
                    sheet.merge_range(mt_row_start, 2, row - 1, 2, mt_rows[0].get("maintask_name", mt_key),
                                      colored_format)
                else:
                    sheet.write(mt_row_start, 2, mt_rows[0].get("maintask_name", mt_key), colored_format)
            # Merge Employee
            if row - emp_row_start > 1:
                sheet.merge_range(emp_row_start, 1, row - 1, 1, emp_key, center_format)
            else:
                sheet.write(emp_row_start, 1, emp_key, center_format)

        if row - team_row_start > 1:
            sheet.merge_range(team_row_start, 0, row - 1, 0, team_key, center_format)
        else:
            sheet.write(team_row_start, 0, team_key, center_format)

    row += 1
    sheet.write(row, 0, "From date", header_format)
    sheet.write(row, 1, "To date", header_format)
    sheet.write(row, 2, "Total Holiday", header_format)
    sheet.write(row, 3, "Total Working Hours", header_format)
    sheet.write(row, 4, "Working Hours\n(In minutes)", header_format)

    row += 1
    additional_data_row = row
    from_date = date_change_format(from_date)
    to_date = date_change_format(to_date)
    sheet.write(additional_data_row, 0, from_date, additional_data_format)
    sheet.write(additional_data_row, 1, to_date, additional_data_format)
    sheet.write(additional_data_row, 2, total_holiday, additional_data_format)
    sheet.write_number(additional_data_row, 3, total_working_hours, additional_data_format)
    # excel_row = row + 1
    sheet.write_formula(additional_data_row, 4, f'=D{additional_data_row+1}*60', additional_data_format)

    row += 2
    sheet.write(row, 0, "MainTask", header_format)
    sheet.write(row, 1, "Task", header_format)
    sheet.write(row, 2, "SubTask", header_format)
    sheet.write(row, 3, "SubTask Type", header_format)
    sheet.write(row, 4, "SubTask Value", header_format)
    sheet.write(row, 5, "SubTask Target Time (Minutes)", header_format)
    sheet.write(row, 6, "Average SubTask Value", header_format)
    sheet.write(row, 7, "Total SubTask Target Time (Minutes)", header_format)
    row += 1
    # Buat set untuk menyaring kombinasi unik
    unique_subtasks = set()

    # Simpan kombinasi unik ke list baru
    unique_rows = []

    for row_data in data:
        key = (row_data["maintask"], row_data["tasks"], row_data["subtask"])
        if key not in unique_subtasks:
            unique_subtasks.add(key)
            unique_rows.append(row_data)

    unique_rows.sort(key=lambda x: (x["maintask"], x["tasks"]))

    for mt_key, mt_rows in groupby(unique_rows, key=lambda x: x["maintask"]):
        mt_rows = list(mt_rows)
        mt_row_start = row

        if mt_key not in main_task_color_map:
            hash_val = int(hashlib.md5(mt_key.encode()).hexdigest(), 16)
            color = base_colors[hash_val % len(base_colors)]
            main_task_color_map[mt_key] = color

        bg_color = main_task_color_map[mt_key]
        if bg_color not in format_cache:
            format_cache[bg_color] = workbook.add_format({
                'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                'border': 1, 'bg_color': bg_color
            })
        colored_format = format_cache[bg_color]

        for t_key, t_rows in groupby(mt_rows, key=lambda x: x["tasks"]):
            t_rows = list(t_rows)
            t_row_start = row
            for tr in t_rows:
                sheet.write(row, 2, tr["subtask_name"], colored_format)
                sheet.write(row, 3, tr["subtask_types"], colored_format)
                sheet.write_number(row, 4, int(tr["value_subtask"]), colored_format)
                sheet.write_number(row, 5, int(tr["target_time_minutes"]), colored_format)
                row += 1

            if row - t_row_start > 1:
                sheet.merge_range(t_row_start, 1, row - 1, 1, t_rows[0].get("task_name", t_key), colored_format)
            else:
                sheet.write(t_row_start, 1, t_rows[0].get("task_name", t_key), colored_format)

        if row - mt_row_start > 1:
            sheet.merge_range(mt_row_start, 0, row - 1, 0, mt_rows[0].get("maintask_name", mt_key), colored_format)
            sheet.merge_range(mt_row_start, 6, row - 1, 6, f'=AVERAGE(E{mt_row_start+1}:E{row})', colored_format)
            sheet.merge_range(mt_row_start, 7, row - 1, 7, f'=SUM(F{mt_row_start+1}:F{row})', colored_format)
            # sheet.merge_range(mt_row_start, 7, row - 1, 7, f'=SUM(F{mt_row_start+1}:F{row})', colored_format)
            # sheet.merge_range(mt_row_start, 8, row - 1, 8, f'=H{mt_row_start+1}/E{additional_data_row+1}', colored_format)
            # sheet.merge_range(mt_row_start, 9, row - 1, 9, f'=G{mt_row_start+1}*I{mt_row_start+1}', colored_format)
        else:
            sheet.write(mt_row_start, 0, mt_rows[0].get("maintask_name", mt_key), colored_format)
            sheet.write_formula(mt_row_start, 6, f'=AVERAGE(E{row}:E{row})', colored_format)
            sheet.write_formula(mt_row_start, 7, f'=SUM(F{row}:F{row})', colored_format)
            # sheet.write_formula(mt_row_start, 7, f'=SUM(F{row}:F{row})', colored_format)
            # sheet.write_formula(mt_row_start, 8, f'=H{row}/E{additional_data_row+1}', colored_format)
            # sheet.write_formula(mt_row_start, 9, f'=G{row}*I{row}', colored_format)

    workbook.close()
    output.seek(0)

    frappe.response["filename"] = f"Report {team_filename} {from_date} -  {to_date}.xlsx"
    frappe.response["filecontent"] = output.read()
    frappe.response["type"] = "binary"
