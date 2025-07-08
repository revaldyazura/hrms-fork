import frappe
import xlsxwriter
import dateparser
from io import BytesIO
from datetime import datetime, timedelta
from itertools import groupby


def calculate_working_hours(from_date_str, to_date_str, holiday_list_name):
    from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
    to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()

    # holidays = frappe.get_all(
    #     "Holiday",
    #     filters={"parent": holiday_list_name},
    #     fields=["holiday_date"]
    # )
    # holiday_dates = {h["holiday_date"] for h in holidays}

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
def export_evaluation_with_average(filters=None):
    filters = frappe.parse_json(filters or '{}')

    query = """SELECT pic_subtask_name,
        maintask_name, task_name,
                      subtask_name,
        value_subtask,
                          performance,
                      final_target_time,
                      contribution
               FROM `tabEvaluation` \
            """

    conditions = []
    values = {}
    from_date = None
    to_date = None

    if filters.get("pic_subtask"):
        conditions.append("pic_subtask = %(pic_subtask)s")
        values["pic_subtask"] = filters["pic_subtask"]
    if filters.get("from_date") and filters.get("to_date"):
        from_date = filters.get("from_date")
        to_date = filters.get("to_date")
        conditions.append("subtask_open_date BETWEEN %(from_date)s AND %(to_date)s")
        # conditions.append("due_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters["from_date"]
        values["to_date"] = filters["to_date"]

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    # print(f'query {query}\nConditions eval report pic {conditions}')
    data = frappe.db.sql(query, values, as_dict=True)

    total_working_hours, total_holiday = calculate_working_hours(from_date, to_date,
                                                  'Annual Holiday') if to_date and from_date else 0


    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    sheet = workbook.add_worksheet("Report Individu")

    bold_format = workbook.add_format({'bold': True})
    center_format = workbook.add_format({ 'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'border': 1})
    header_format = workbook.add_format({ 'bold': True, 'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'border': 1})
    sheet.set_column("A:H", 20)

    headers = ["Employee", "MainTask", "Task","SubTask", "Value SubTask", "Performance", "Final Target Time", "Final Contribution"]
    for col, h in enumerate(headers):
        sheet.write(0, col, h, header_format)

    start_row = 1
    row = start_row

    data.sort(key=lambda x: (x["pic_subtask_name"], x["maintask_name"], x["task_name"]))

    for emp_key, emp_rows in groupby(data, key=lambda x: x["pic_subtask_name"]):
        emp_rows = list(emp_rows)
        emp_row_start = row
        for mt_key, mt_rows in groupby(emp_rows, key=lambda x: x["maintask_name"]):
            mt_rows = list(mt_rows)
            mt_row_start = row
            for t_key, t_rows in groupby(mt_rows, key=lambda x: x["task_name"]):
                t_rows = list(t_rows)
                t_row_start = row
                for tr in t_rows:
                    sheet.write(row, 3, tr["subtask_name"], center_format)
                    sheet.write_number(row, 4, int(tr["value_subtask"]), center_format)
                    sheet.write_number(row, 5, tr["performance"], center_format)
                    sheet.write_number(row, 6, tr["final_target_time"], center_format)
                    try:
                        contrib = float(tr["contribution"].replace("%", "")) if isinstance(tr["contribution"],
                                                                                           str) else float(
                            tr["contribution"])
                    except:
                        contrib = 0
                    sheet.write(row, 7, contrib, center_format)
                    row += 1
                # Merge Task
                if row - t_row_start > 1:
                    sheet.merge_range(t_row_start, 2, row - 1, 2, t_key, center_format)
                else:
                    sheet.write(t_row_start, 2, t_key, center_format)
            # Merge Main Task
            if row - mt_row_start > 1:
                sheet.merge_range(mt_row_start, 1, row - 1, 1, mt_key, center_format)
            else:
                sheet.write(mt_row_start, 1, mt_key, center_format)
        # Merge Employee
        if row - emp_row_start > 1:
            sheet.merge_range(emp_row_start, 0, row - 1, 0, emp_key, center_format)
        else:
            sheet.write(emp_row_start, 0, emp_key, center_format)

    data_row = row
    sheet.merge_range(row, 0, row, 3, "Average", header_format)
    sheet.write_formula(row, 4, f'=AVERAGE(E2:E{data_row})', center_format)
    sheet.write_formula(row, 5, f'=AVERAGE(F2:F{data_row})', center_format)
    sheet.write_formula(row, 6, f'=AVERAGE(G2:G{data_row})', center_format)
    sheet.write_formula(row, 7, f'=AVERAGE(H2:H{data_row})', center_format)
    row+=2

    sheet.write(row, 0, "From date", header_format)
    sheet.write(row, 1, "To date", header_format)
    sheet.write(row, 2, "Total Working Hours", header_format)
    sheet.write(row, 3, "Working Hours\n(In minutes)", header_format)
    sheet.write(row, 4, "Total Target Time", header_format)
    sheet.write(row, 5, "Load", header_format)
    sheet.write(row, 6, "Final Load", header_format)

    row+=1
    from_date = date_change_format(from_date)
    to_date = date_change_format(to_date)
    sheet.write(row, 0, from_date, center_format)
    sheet.write(row, 1, to_date, center_format)
    sheet.write_number(row, 2, total_working_hours, center_format)
    excel_row = row + 1
    sheet.write_formula(row, 3, f'=C{excel_row}*60', center_format)
    sheet.write_formula(row, 4, f'=SUM(G2:G{data_row})', center_format)
    sheet.write_formula(row, 5, f'=E{excel_row}/D{excel_row}', center_format)
    sheet.write_formula(row, 6, f'=E{data_row+1}*F{excel_row}', center_format)

    row+=1
    sheet.write(row, 0, "Total Holiday", header_format)
    sheet.write(row, 1, total_holiday, center_format)

    workbook.close()
    output.seek(0)

    frappe.response["filename"] = f"Report Individu {from_date} -  {to_date}.xlsx"
    frappe.response["filecontent"] = output.read()
    frappe.response["type"] = "binary"
