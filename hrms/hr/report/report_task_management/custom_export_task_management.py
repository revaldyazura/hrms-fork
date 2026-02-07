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
    from_date = datetime.strptime(from_date_str, "%Y-%m-%d %H:%M:%S").date()
    to_date = datetime.strptime(to_date_str, "%Y-%m-%d %H:%M:%S").date()

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


def create_formats(workbook):
    """Create and return commonly used xlsxwriter formats and constants.

    Returns a dict with keys:
      - bold_format
      - center_format
      - header_format
      - additional_data_format
      - base_colors
    """
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

    return {
        'bold_format': bold_format,
        'center_format': center_format,
        'base_colors': base_colors,
        'header_format': header_format,
        'additional_data_format': additional_data_format,
    }


def write_report_sheet(workbook, data, from_date, to_date, total_working_hours, total_holiday, team_filename, filter_by_open_date, plain_export):
    """Write the main report sheet into `workbook` using provided data and meta.

    This extracts the large inline block that formats and writes the Excel sheet.
    """
    sheet = workbook.add_worksheet(f"Report {team_filename}")

    formats = create_formats(workbook)
    bold_format = formats['bold_format']
    center_format = formats['center_format']
    base_colors = formats['base_colors']
    header_format = formats['header_format']
    additional_data_format = formats['additional_data_format']
    main_task_color_map = {}
    format_cache = {}
    sheet.set_column("A:K", 20)

    if filter_by_open_date:
        headers = ["Team", "Employee", "MainTask", "Task", "SubTask", "SubTask Type", "SubTask Value", "SubTask Target Time (Minutes)", "SubTask Status", "SubTask Open Date", "SubTask Done Date"]
    else:
        headers = ["Team", "Employee", "MainTask", "Task", "SubTask", "SubTask Type", "SubTask Value", "SubTask Target Time (Minutes)", "SubTask Status", "SubTask Start Date", "SubTask Done Date"]
    for col, h in enumerate(headers):
        sheet.write(0, col, h, header_format)

    start_row = 1
    row = start_row

    data.sort(key=lambda x: (x.get("team"), x.get("pic_subtask_name"), x.get("maintask"), x.get("tasks")))

    if plain_export:
        for tr in data:
            mt_key = tr.get("maintask")
            if mt_key not in main_task_color_map:
                hash_val = int(hashlib.md5(str(mt_key).encode()).hexdigest(), 16)
                color = base_colors[hash_val % len(base_colors)]
                main_task_color_map[mt_key] = color

            bg_color = main_task_color_map[mt_key]
            if bg_color not in format_cache:
                format_cache[bg_color] = workbook.add_format({
                    'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                    'border': 1, 'bg_color': bg_color
                })
            colored_format = format_cache[bg_color]

            sheet.write(row, 0, tr.get("team"), colored_format)
            sheet.write(row, 1, tr.get("pic_subtask_name"), colored_format)
            sheet.write(row, 2, tr.get("maintask_name") or tr.get("maintask"), colored_format)
            sheet.write(row, 3, tr.get("task_name") or tr.get("tasks"), colored_format)
            sheet.write(row, 4, tr.get("subtask_name"), colored_format)
            sheet.write(row, 5, tr.get("subtask_types"), colored_format)
            sheet.write_number(row, 6, int(tr.get("value_subtask") or 0), colored_format)
            sheet.write_number(row, 7, int(tr.get("target_time_minutes") or 0), colored_format)
            sheet.write(row, 8, tr.get("subtask_status"), colored_format)
            if filter_by_open_date:
                sheet.write(
                    row,
                    9,
                    date_change_format(tr.get("subtask_open_date")) if tr.get("subtask_open_date") else "",
                    colored_format,
                )
            else:
                sheet.write(
                    row,
                    9,
                    date_change_format(tr.get("subtask_start_date")) if tr.get("subtask_start_date") else "",
                    colored_format,
                )
            sheet.write(
                row,
                10,
                date_change_format(tr.get("subtask_done_date")) if tr.get("subtask_done_date") else "",
                colored_format,
            )
            row += 1
    else:
        for team_key, team_rows in groupby(data, key=lambda x: x.get("team")):
            team_rows = list(team_rows)
            team_row_start = row
            for emp_key, emp_rows in groupby(team_rows, key=lambda x: x.get("pic_subtask_name")):
                emp_rows = list(emp_rows)
                emp_row_start = row
                for mt_key, mt_rows in groupby(emp_rows, key=lambda x: x.get("maintask")):
                    mt_rows = list(mt_rows)
                    mt_row_start = row
                    if mt_key not in main_task_color_map:
                        hash_val = int(hashlib.md5(str(mt_key).encode()).hexdigest(), 16)
                        color = base_colors[hash_val % len(base_colors)]
                        main_task_color_map[mt_key] = color

                    bg_color = main_task_color_map[mt_key]
                    if bg_color not in format_cache:
                        format_cache[bg_color] = workbook.add_format({
                            'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                            'border': 1, 'bg_color': bg_color
                        })
                    colored_format = format_cache[bg_color]

                    for t_key, t_rows in groupby(mt_rows, key=lambda x: x.get("tasks")):
                        t_rows = list(t_rows)
                        t_row_start = row
                        for tr in t_rows:
                            sheet.write(row, 4, tr.get("subtask_name"), colored_format)
                            sheet.write(row, 5, tr.get("subtask_types"), colored_format)
                            sheet.write_number(row, 6, int(tr.get("value_subtask") or 0), colored_format)
                            sheet.write_number(row, 7, int(tr.get("target_time_minutes") or 0), colored_format)
                            sheet.write(row, 8, tr.get("subtask_status"), colored_format)
                            if filter_by_open_date:
                                sheet.write(row, 9, date_change_format(tr.get("subtask_open_date")) if tr.get("subtask_open_date") else "", colored_format)
                            else:
                                sheet.write(row, 9, date_change_format(tr.get("subtask_start_date")) if tr.get("subtask_start_date") else "", colored_format)
                            sheet.write(row, 10, date_change_format(tr.get("subtask_done_date")) if tr.get("subtask_done_date") else "", colored_format)
                            row += 1

                        # Merge Task
                        if row - t_row_start > 1:
                            sheet.merge_range(t_row_start, 3, row - 1, 3, t_rows[0].get("task_name", t_key), colored_format)
                        else:
                            sheet.write(t_row_start, 3, t_rows[0].get("task_name", t_key), colored_format)
                    # Merge Main Task
                    if row - mt_row_start > 1:
                        sheet.merge_range(mt_row_start, 2, row - 1, 2, mt_rows[0].get("maintask_name", mt_key), colored_format)
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
    from_date_fmt = date_change_format(from_date) if from_date else ""
    to_date_fmt = date_change_format(to_date) if to_date else ""
    sheet.write(additional_data_row, 0, from_date_fmt, additional_data_format)
    sheet.write(additional_data_row, 1, to_date_fmt, additional_data_format)
    sheet.write(additional_data_row, 2, total_holiday, additional_data_format)
    sheet.write_number(additional_data_row, 3, total_working_hours, additional_data_format)
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
        key = (row_data.get("maintask"), row_data.get("tasks"), row_data.get("subtask"))
        if key not in unique_subtasks:
            unique_subtasks.add(key)
            unique_rows.append(row_data)

    unique_rows.sort(key=lambda x: (x.get("maintask"), x.get("tasks")))

    for mt_key, mt_rows in groupby(unique_rows, key=lambda x: x.get("maintask")):
        mt_rows = list(mt_rows)
        mt_row_start = row

        if mt_key not in main_task_color_map:
            hash_val = int(hashlib.md5(str(mt_key).encode()).hexdigest(), 16)
            color = base_colors[hash_val % len(base_colors)]
            main_task_color_map[mt_key] = color

        bg_color = main_task_color_map[mt_key]
        if bg_color not in format_cache:
            format_cache[bg_color] = workbook.add_format({
                'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                'border': 1, 'bg_color': bg_color
            })
        colored_format = format_cache[bg_color]

        for t_key, t_rows in groupby(mt_rows, key=lambda x: x.get("tasks")):
            t_rows = list(t_rows)
            t_row_start = row
            for tr in t_rows:
                if plain_export:
                    sheet.write(row, 0, tr.get("maintask_name") or tr.get("maintask"), colored_format)
                    sheet.write(row, 1, tr.get("task_name") or tr.get("tasks"), colored_format)
                sheet.write(row, 2, tr.get("subtask_name"), colored_format)
                sheet.write(row, 3, tr.get("subtask_types"), colored_format)
                sheet.write_number(row, 4, int(tr.get("value_subtask") or 0), colored_format)
                sheet.write_number(row, 5, int(tr.get("target_time_minutes") or 0), colored_format)
                row += 1

            if not plain_export:
                if row - t_row_start > 1:
                    sheet.merge_range(t_row_start, 1, row - 1, 1, t_rows[0].get("task_name", t_key), colored_format)
                else:
                    sheet.write(t_row_start, 1, t_rows[0].get("task_name", t_key), colored_format)

        if plain_export:
            # No merges: write the aggregate formulas on the first row only.
            if row - mt_row_start >= 1:
                sheet.write_formula(mt_row_start, 6, f'=AVERAGE(E{mt_row_start+1}:E{row})', colored_format)
                sheet.write_formula(mt_row_start, 7, f'=SUM(F{mt_row_start+1}:F{row})', colored_format)
        else:
            if row - mt_row_start > 1:
                sheet.merge_range(mt_row_start, 0, row - 1, 0, mt_rows[0].get("maintask_name", mt_key), colored_format)
                sheet.merge_range(mt_row_start, 6, row - 1, 6, f'=AVERAGE(E{mt_row_start+1}:E{row})', colored_format)
                sheet.merge_range(mt_row_start, 7, row - 1, 7, f'=SUM(F{mt_row_start+1}:F{row})', colored_format)
            else:
                sheet.write(mt_row_start, 0, mt_rows[0].get("maintask_name", mt_key), colored_format)
                sheet.write_formula(mt_row_start, 6, f'=AVERAGE(E{row}:E{row})', colored_format)
                sheet.write_formula(mt_row_start, 7, f'=SUM(F{row}:F{row})', colored_format)


def write_report_sheets_by_pic(workbook, data, from_date, to_date, total_working_hours, total_holiday, filter_by_open_date, plain_export):
    """Write separate report sheets per PIC into `workbook`.

    Each PIC (st.pic_subtask_name) gets its own sheet, with the
    same layout and aggregation as the main report.
    """

    formats = create_formats(workbook)
    bold_format = formats['bold_format']
    center_format = formats['center_format']
    base_colors = formats['base_colors']
    header_format = formats['header_format']
    additional_data_format = formats['additional_data_format']

    # Sort terlebih dahulu untuk groupby yang stabil
    data.sort(key=lambda x: (x.get("pic_subtask_name"), x.get("team"), x.get("maintask"), x.get("tasks")))

    for emp_key, emp_rows in groupby(data, key=lambda x: x.get("pic_subtask_name")):
        emp_rows = list(emp_rows)

        # Nama sheet: satu sheet per PIC, dibatasi 31 karakter (batas Excel)
        sheet_label = emp_key or "Unknown"
        sheet_name = f"{sheet_label}"[:31]
        sheet = workbook.add_worksheet(sheet_name)

        main_task_color_map = {}
        format_cache = {}

        sheet.set_column("A:K", 20)

        if filter_by_open_date:
            headers = [
                "Team", "Employee", "MainTask", "Task", "SubTask", "SubTask Type",
                "SubTask Value", "SubTask Target Time (Minutes)", "SubTask Status",
                "SubTask Open Date", "SubTask Done Date",
            ]
        else:
            headers = [
                "Team", "Employee", "MainTask", "Task", "SubTask", "SubTask Type",
                "SubTask Value", "SubTask Target Time (Minutes)", "SubTask Status",
                "SubTask Start Date", "SubTask Done Date",
            ]
        for col, h in enumerate(headers):
            sheet.write(0, col, h, header_format)

        start_row = 1
        row = start_row

        if plain_export:
            for tr in emp_rows:
                mt_key = tr.get("maintask")
                if mt_key not in main_task_color_map:
                    hash_val = int(hashlib.md5(str(mt_key).encode()).hexdigest(), 16)
                    color = base_colors[hash_val % len(base_colors)]
                    main_task_color_map[mt_key] = color

                bg_color = main_task_color_map[mt_key]
                if bg_color not in format_cache:
                    format_cache[bg_color] = workbook.add_format({
                        'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                        'border': 1, 'bg_color': bg_color,
                    })
                colored_format = format_cache[bg_color]

                sheet.write(row, 0, tr.get("team"), colored_format)
                sheet.write(row, 1, tr.get("pic_subtask_name"), colored_format)
                sheet.write(row, 2, tr.get("maintask_name") or tr.get("maintask"), colored_format)
                sheet.write(row, 3, tr.get("task_name") or tr.get("tasks"), colored_format)
                sheet.write(row, 4, tr.get("subtask_name"), colored_format)
                sheet.write(row, 5, tr.get("subtask_types"), colored_format)
                sheet.write_number(row, 6, int(tr.get("value_subtask") or 0), colored_format)
                sheet.write_number(row, 7, int(tr.get("target_time_minutes") or 0), colored_format)
                sheet.write(row, 8, tr.get("subtask_status"), colored_format)
                if filter_by_open_date:
                    sheet.write(
                        row,
                        9,
                        date_change_format(tr.get("subtask_open_date"))
                        if tr.get("subtask_open_date")
                        else "",
                        colored_format,
                    )
                else:
                    sheet.write(
                        row,
                        9,
                        date_change_format(tr.get("subtask_start_date"))
                        if tr.get("subtask_start_date")
                        else "",
                        colored_format,
                    )
                sheet.write(
                    row,
                    10,
                    date_change_format(tr.get("subtask_done_date"))
                    if tr.get("subtask_done_date")
                    else "",
                    colored_format,
                )
                row += 1
        else:
            for team_key, team_rows in groupby(emp_rows, key=lambda x: x.get("team")):
                team_rows = list(team_rows)
                team_row_start = row

                for mt_key, mt_rows in groupby(team_rows, key=lambda x: x.get("maintask")):
                    mt_rows = list(mt_rows)
                    mt_row_start = row

                    if mt_key not in main_task_color_map:
                        hash_val = int(hashlib.md5(str(mt_key).encode()).hexdigest(), 16)
                        color = base_colors[hash_val % len(base_colors)]
                        main_task_color_map[mt_key] = color

                    bg_color = main_task_color_map[mt_key]
                    if bg_color not in format_cache:
                        format_cache[bg_color] = workbook.add_format({
                            'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                            'border': 1, 'bg_color': bg_color,
                        })
                    colored_format = format_cache[bg_color]

                    for t_key, t_rows in groupby(mt_rows, key=lambda x: x.get("tasks")):
                        t_rows = list(t_rows)
                        t_row_start = row

                        for tr in t_rows:
                            sheet.write(row, 4, tr.get("subtask_name"), colored_format)
                            sheet.write(row, 5, tr.get("subtask_types"), colored_format)
                            sheet.write_number(row, 6, int(tr.get("value_subtask") or 0), colored_format)
                            sheet.write_number(row, 7, int(tr.get("target_time_minutes") or 0), colored_format)
                            sheet.write(row, 8, tr.get("subtask_status"), colored_format)
                            if filter_by_open_date:
                                sheet.write(
                                    row,
                                    9,
                                    date_change_format(tr.get("subtask_open_date"))
                                    if tr.get("subtask_open_date")
                                    else "",
                                    colored_format,
                                )
                            else:
                                sheet.write(
                                    row,
                                    9,
                                    date_change_format(tr.get("subtask_start_date"))
                                    if tr.get("subtask_start_date")
                                    else "",
                                    colored_format,
                                )
                            sheet.write(
                                row,
                                10,
                                date_change_format(tr.get("subtask_done_date"))
                                if tr.get("subtask_done_date")
                                else "",
                                colored_format,
                            )
                            row += 1

                        # Merge Task
                        if row - t_row_start > 1:
                            sheet.merge_range(
                                t_row_start,
                                3,
                                row - 1,
                                3,
                                t_rows[0].get("task_name", t_key),
                                colored_format,
                            )
                        else:
                            sheet.write(
                                t_row_start,
                                3,
                                t_rows[0].get("task_name", t_key),
                                colored_format,
                            )

                    # Merge Main Task
                    if row - mt_row_start > 1:
                        sheet.merge_range(
                            mt_row_start,
                            2,
                            row - 1,
                            2,
                            mt_rows[0].get("maintask_name", mt_key),
                            colored_format,
                        )
                    else:
                        sheet.write(
                            mt_row_start,
                            2,
                            mt_rows[0].get("maintask_name", mt_key),
                            colored_format,
                        )

                # Merge Employee (kolom 1) untuk seluruh blok team ini
                if row - team_row_start > 1:
                    sheet.merge_range(
                        team_row_start,
                        1,
                        row - 1,
                        1,
                        emp_key,
                        center_format,
                    )
                else:
                    sheet.write(team_row_start, 1, emp_key, center_format)

                # Merge Team (kolom 0)
                if row - team_row_start > 1:
                    sheet.merge_range(
                        team_row_start,
                        0,
                        row - 1,
                        0,
                        team_key,
                        center_format,
                    )
                else:
                    sheet.write(team_row_start, 0, team_key, center_format)

        # Bagian summary di bawah per sheet PIC
        row += 1
        sheet.write(row, 0, "From date", header_format)
        sheet.write(row, 1, "To date", header_format)
        sheet.write(row, 2, "Total Holiday", header_format)
        sheet.write(row, 3, "Total Working Hours", header_format)
        sheet.write(row, 4, "Working Hours\n(In minutes)", header_format)

        row += 1
        additional_data_row = row
        from_date_fmt = date_change_format(from_date) if from_date else ""
        to_date_fmt = date_change_format(to_date) if to_date else ""
        sheet.write(additional_data_row, 0, from_date_fmt, additional_data_format)
        sheet.write(additional_data_row, 1, to_date_fmt, additional_data_format)
        sheet.write(additional_data_row, 2, total_holiday, additional_data_format)
        sheet.write_number(additional_data_row, 3, total_working_hours, additional_data_format)
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
        unique_subtasks = set()
        unique_rows = []

        for row_data in emp_rows:
            key = (
                row_data.get("maintask"),
                row_data.get("tasks"),
                row_data.get("subtask"),
            )
            if key not in unique_subtasks:
                unique_subtasks.add(key)
                unique_rows.append(row_data)

        unique_rows.sort(key=lambda x: (x.get("maintask"), x.get("tasks")))

        for mt_key, mt_rows in groupby(unique_rows, key=lambda x: x.get("maintask")):
            mt_rows = list(mt_rows)
            mt_row_start = row

            if mt_key not in main_task_color_map:
                hash_val = int(hashlib.md5(str(mt_key).encode()).hexdigest(), 16)
                color = base_colors[hash_val % len(base_colors)]
                main_task_color_map[mt_key] = color

            bg_color = main_task_color_map[mt_key]
            if bg_color not in format_cache:
                format_cache[bg_color] = workbook.add_format({
                    'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                    'border': 1, 'bg_color': bg_color,
                })
            colored_format = format_cache[bg_color]

            for t_key, t_rows in groupby(mt_rows, key=lambda x: x.get("tasks")):
                t_rows = list(t_rows)
                t_row_start = row
                for tr in t_rows:
                    if plain_export:
                        sheet.write(row, 0, tr.get("maintask_name") or tr.get("maintask"), colored_format)
                        sheet.write(row, 1, tr.get("task_name") or tr.get("tasks"), colored_format)
                    sheet.write(row, 2, tr.get("subtask_name"), colored_format)
                    sheet.write(row, 3, tr.get("subtask_types"), colored_format)
                    sheet.write_number(row, 4, int(tr.get("value_subtask") or 0), colored_format)
                    sheet.write_number(row, 5, int(tr.get("target_time_minutes") or 0), colored_format)
                    row += 1

                if not plain_export:
                    if row - t_row_start > 1:
                        sheet.merge_range(
                            t_row_start,
                            1,
                            row - 1,
                            1,
                            t_rows[0].get("task_name", t_key),
                            colored_format,
                        )
                    else:
                        sheet.write(
                            t_row_start,
                            1,
                            t_rows[0].get("task_name", t_key),
                            colored_format,
                        )

            if plain_export:
                if row - mt_row_start >= 1:
                    sheet.write_formula(
                        mt_row_start,
                        6,
                        f'=AVERAGE(E{mt_row_start+1}:E{row})',
                        colored_format,
                    )
                    sheet.write_formula(
                        mt_row_start,
                        7,
                        f'=SUM(F{mt_row_start+1}:F{row})',
                        colored_format,
                    )
            else:
                if row - mt_row_start > 1:
                    sheet.merge_range(
                        mt_row_start,
                        0,
                        row - 1,
                        0,
                        mt_rows[0].get("maintask_name", mt_key),
                        colored_format,
                    )
                    sheet.merge_range(
                        mt_row_start,
                        6,
                        row - 1,
                        6,
                        f'=AVERAGE(E{mt_row_start+1}:E{row})',
                        colored_format,
                    )
                    sheet.merge_range(
                        mt_row_start,
                        7,
                        row - 1,
                        7,
                        f'=SUM(F{mt_row_start+1}:F{row})',
                        colored_format,
                    )
                else:
                    sheet.write(
                        mt_row_start,
                        0,
                        mt_rows[0].get("maintask_name", mt_key),
                        colored_format,
                    )
                    sheet.write_formula(
                        mt_row_start,
                        6,
                        f'=AVERAGE(E{row}:E{row})',
                        colored_format,
                    )
                    sheet.write_formula(
                        mt_row_start,
                        7,
                        f'=SUM(F{row}:F{row})',
                        colored_format,
                    )


@frappe.whitelist()
def export_team_task_management(filters=None):
    filters = frappe.parse_json(filters or '{}')

    query = """SELECT st.pic_subtask,
                    st.pic_subtask_name,
                      st.maintask,
                      st.maintask_name,
                      st.tasks,
                      st.tasks_name AS task_name,
                      st.name AS subtask,
                      st.subtask_name,
                      st.value AS value_subtask,
                      st.target_time_minutes,
                      st.status AS subtask_status,
                      st.subtask_open_date,
                      st.subtask_start_date,
                      st.subtask_done_date,
                      emp.team
               FROM `tabSubTask` st
                                                LEFT JOIN `tabEmployee` emp ON emp.name = st.pic_subtask \
            """

    conditions = []
    values = {}
    from_date = None
    to_date = None

    if filters.get("team"):
        conditions.append("emp.team = %(team)s")
        values["team"] = filters["team"]
    if filters.get("from_date") and filters.get("to_date"):
        from_date = filters.get("from_date")
        to_date = filters.get("to_date")
        if filters.get('filter_by_open_date'):
            conditions.append("st.subtask_open_date BETWEEN %(from_date)s AND %(to_date)s")
        else:
            conditions.append("st.subtask_start_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters["from_date"]
        values["to_date"] = filters["to_date"]

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    data = frappe.db.sql(query, values, as_dict=True)
    # Ambil peta subtask_type sekali saja untuk menghindari N+1 query
    subtask_type_map = get_subtask_type_map()
    for row in data:
        row["subtask_types"] = subtask_type_map.get(row["subtask"], "")
    team_filename = data[0].get('team') if data else filters.get('team')

    total_working_hours, total_holiday = calculate_working_hours(
        from_date, to_date, 'Annual Holiday'
    ) if to_date and from_date else (0, 0)

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Jika flag `separate_sheets_by_pic` tidak aktif, tulis satu sheet utama
    if not filters.get('separate_sheets_by_pic'):
        write_report_sheet(
            workbook,
            data,
            from_date,
            to_date,
            total_working_hours,
            total_holiday,
            team_filename,
            filter_by_open_date=filters.get('filter_by_open_date', False),
            plain_export=filters.get('plain_export', False)
        )
    else:
        # Jika aktif, buat satu sheet per PIC
        write_report_sheets_by_pic(
            workbook,
            data,
            from_date,
            to_date,
            total_working_hours,
            total_holiday,
            filter_by_open_date=filters.get('filter_by_open_date', False),
            plain_export=filters.get('plain_export', False)
        )

    workbook.close()
    output.seek(0)

    frappe.response["filename"] = f"Report Task Management {team_filename} {from_date} -  {to_date}.xlsx"
    frappe.response["filecontent"] = output.read()
    frappe.response["type"] = "binary"
