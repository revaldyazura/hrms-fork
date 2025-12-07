import frappe

@frappe.whitelist()
def get_maintask_subtask_tracker(maintask: str | None = None):
 
	if not maintask:
		return {"type_columns": [], "type_rows": []}

	# Get status options from SubTask doctype
	meta = frappe.get_meta("SubTask")
	status_field = meta.get_field("status")
	statuses = []
	if status_field and status_field.options:
		statuses = [s.strip() for s in status_field.options.split("\n") if s.strip()]

	# Map display label -> key used in response
	def status_key(label: str) -> str:
		return label.lower().replace(" ", "_")

	# Prepare type_columns dynamically
	type_columns = [{"key": "type", "label": "Type"}]
	for s in statuses:
		type_columns.append({"key": status_key(s), "label": s})
	type_columns.append({"key": "total", "label": "Total"})

	# Fetch relevant SubTasks
	subtasks = frappe.get_all(
		"SubTask",
		filters={"maintask": maintask},
		fields=["name", "status"],
	)

	if not subtasks:
		return {"type_columns": type_columns, "type_rows": []}

	# Aggregate by SubTask Type (child table) per status
	agg = {}
	valid_keys = {status_key(s) for s in statuses}

	for st in subtasks:
		label = (st.get("status") or "").strip()
		key = status_key(label) if label else None
		if not key or key not in valid_keys:
			# Skip unknown statuses
			continue

		child_rows = frappe.get_all(
			"SubTask Type",
			filters={"parent": st["name"], "parenttype": "SubTask"},
			fields=["subtask_type"],
		)
		print(child_rows) 

		for c in child_rows:
			tname = (c.get("subtask_type") or "").strip() or "-"
			if tname not in agg:
				agg[tname] = {k: 0 for k in valid_keys}
			agg[tname][key] += 1

	type_rows = []
	for tname, counts in sorted(agg.items()):
		total = sum(counts.values())
		row = {"type": tname, **counts, "total": total}
		type_rows.append(row)

	# Build priority aggregation using same status keys
	priority_field = meta.get_field("priority")
	priorities = []
	if priority_field and priority_field.options:
		priorities = [p.strip() for p in priority_field.options.split("\n") if p.strip()]

	# Prepare priority columns: first col is Priority label, then statuses, then Total
	p_columns = [{"key": "priority", "label": "Priority"}]
	for s in statuses:
		p_columns.append({"key": status_key(s), "label": s})
	p_columns.append({"key": "total", "label": "Total"})

	p_rows = []
	if subtasks and priorities:
		# Initialize counts per priority
		p_agg = {p: {k: 0 for k in valid_keys} for p in priorities}

		for st in subtasks:
			label = (st.get("status") or "").strip()
			key = status_key(label) if label else None
			if not key or key not in valid_keys:
				continue

			# Get full SubTask doc once to read priority field efficiently
			pr = frappe.db.get_value("SubTask", st["name"], "priority")
			pr_label = (pr or "").strip() or "-"
			if pr_label not in p_agg:
				# In case priority value not in configured options
				p_agg[pr_label] = {k: 0 for k in valid_keys}
			p_agg[pr_label][key] += 1

		for pr_label, counts in p_agg.items():
			total = sum(counts.values())
			p_rows.append({"priority": pr_label, **counts, "total": total})

	# Build PIC SubTask aggregation using same status keys
	pic_columns = [{"key": "pic", "label": "PIC SubTask"}]
	for s in statuses:
		pic_columns.append({"key": status_key(s), "label": s})
	pic_columns.append({"key": "total", "label": "Total"})

	pic_rows = []
	if subtasks:
		pic_agg = {}
		for st in subtasks:
			label = (st.get("status") or "").strip()
			key = status_key(label) if label else None
			if not key or key not in valid_keys:
				continue

			pic_name = frappe.db.get_value("SubTask", st["name"], "pic_subtask_name")
			pname = (pic_name or "").strip() or "-"
			if pname not in pic_agg:
				pic_agg[pname] = {k: 0 for k in valid_keys}
			pic_agg[pname][key] += 1

		for pname, counts in pic_agg.items():
			total = sum(counts.values())
			pic_rows.append({"pic": pname, **counts, "total": total})

	return {
		"type_columns": type_columns,
		"type_rows": type_rows,
		"priority_columns": p_columns,
		"priority_rows": p_rows,
		"pic_columns": pic_columns,
		"pic_rows": pic_rows,
	}
