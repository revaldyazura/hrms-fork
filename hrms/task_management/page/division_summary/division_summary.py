import frappe

@frappe.whitelist()
def get_team_options():
    """Return list opsi Team: label=team_name (fallback name), value=name (docname)."""
    rows = frappe.get_all("Team", fields=["name", "team_name"])
    return [
        {"label": (r.get("team_name") or r.get("name")), "value": r.get("name")}
        for r in rows
        if r.get("name")
    ]


@frappe.whitelist()
def get_team_overview(team: str | None = None, status: str | None = None, start_date: str | None = None, end_date: str | None = None):
    """
    Return merged data for Team Overview page.

    Inputs:
    - team: Team docname or None (means all teams)
    - status: SubTask status filter or None (means all statuses)
    - start_date: (YYYY-MM-DD) lower bound for subtask_start_date (inclusive) or None
    - end_date: (YYYY-MM-DD) upper bound for subtask_start_date (inclusive) or None

    Output JSON structure:
    {
      "employees": [{"name": Employee.name, "employee_name": Employee.employee_name}, ...],
      "subtask_rows": [
           {
             "employee_name": str,
             "maintask_name": str,
             "tasks_name": str,
             "subtask_name": str,
             "priority": str,
             "status": str,
             "start_date": datetime | str | None
           }, ...
      ]
    }

    Notes:
    - When team is provided, only employees with Employee.team == team are returned.
    - When team is None, return all active employees.
    - When status is provided, filter SubTask by that status; otherwise include all statuses.
    - SubTask rows are filtered to subtasks whose PIC is in the returned employees list.
    - Date filtering logic:
        * If both start_date and end_date provided: subtask_start_date BETWEEN start_date AND end_date
        * If only start_date: subtask_start_date >= start_date
        * If only end_date: subtask_start_date <= end_date
    """

    # 1) Fetch employees by team (or all active employees)
    emp_filters = {}
    if team:
        emp_filters["team"] = team
    # Prefer active employees only to avoid noise
    # Many HRMS setups use Employee.status in {"Active", "Left"}
    try:
        emp_filters_with_status = emp_filters.copy()
        emp_filters_with_status["status"] = "Active"
        employees = frappe.get_all(
            "Employee",
            filters=emp_filters_with_status,
            fields=["name", "employee_name"],
            order_by="employee_name asc",
        )
        # If field 'status' doesn't exist in this deployment, fall back without it
        if not employees:
            employees = frappe.get_all(
                "Employee",
                filters=emp_filters,
                fields=["name", "employee_name"],
                order_by="employee_name asc",
            )
    except Exception:
        employees = frappe.get_all(
            "Employee",
            filters=emp_filters,
            fields=["name", "employee_name"],
            order_by="employee_name asc",
        )

    # Ensure list type
    employees = employees or []
    emp_ids = [e.get("name") for e in employees if e.get("name")]

    # 2) Build filters for SubTask
    # Build filter list for SubTask (use list to allow multiple conditions on same field)
    if not emp_ids:
        return {"employees": employees, "subtask_rows": []}

    st_filters_list = []
    if status:
        st_filters_list.append(["status", "=", status])
    st_filters_list.append(["pic_subtask", "in", emp_ids])
    # Date range filters (subtask_start_date is a Datetime field)
    # Validate date format lightly; if malformed, ignore that bound.
    def _valid_date(d: str | None) -> str | None:
        if not d:
            return None
        try:
            frappe.utils.getdate(d)  # raises if invalid
            return d
        except Exception:
            return None

    start_date_v = _valid_date(start_date)
    end_date_v = _valid_date(end_date)
    if start_date_v and end_date_v:
        # Ensure logical order; if end before start, swap or drop end.
        if frappe.utils.getdate(end_date_v) < frappe.utils.getdate(start_date_v):
            # Drop end_date to keep >= start logic (frontend should prevent this)
            end_date_v = None
    if start_date_v and end_date_v:
        st_filters_list.append(["subtask_start_date", ">=", start_date_v])
        st_filters_list.append(["subtask_start_date", "<=", end_date_v])
    elif start_date_v:
        st_filters_list.append(["subtask_start_date", ">=", start_date_v])
    elif end_date_v:
        st_filters_list.append(["subtask_start_date", "<=", end_date_v])

    # 3) Fetch subtasks
    subtasks = frappe.get_all(
        "SubTask",
        filters=st_filters_list if st_filters_list else {},
        fields=[
            "name",
            "pic_subtask",
            "pic_subtask_name",
            "maintask_name",
            "tasks_name",
            "subtask_name",
            "priority",
            "status",
            "subtask_start_date",
        ],
        order_by="pic_subtask_name asc, subtask_start_date asc",
    )

    # 4) Shape rows for UI
    subtask_rows = []
    for r in (subtasks or []):
        subtask_rows.append({
            "employee_name": r.get("pic_subtask_name") or "-",
            "maintask_name": r.get("maintask_name") or "-",
            "tasks_name": r.get("tasks_name") or "-",
            "subtask_name": r.get("subtask_name") or "-",
            "priority": r.get("priority") or "-",
            "status": r.get("status") or "-",
            "start_date": r.get("subtask_start_date") or None,
        })

    return {
        "employees": employees,
        "subtask_rows": subtask_rows,
    }