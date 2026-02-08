frappe.pages['evaluate-subtasks'].on_page_load = function (wrapper) {
	if (!document.getElementById('evaluate-subtasks-style')) {
		const style = document.createElement('style');
		style.id = 'evaluate-subtasks-style';
		style.textContent = `
			.evaluate-subtasks-page .evaluate-subtasks-table,
			.evaluate-subtasks-page .datatable-wrapper {
				margin-top: 12px;
				overflow-x: auto;
			}
			.evaluate-subtasks-page .dt-scrollable {
				overflow-x: auto !important;
			}
			/* frappe-datatable uses flex rows; ensure rows can exceed container width */
			.evaluate-subtasks-page .datatable .dt-header .dt-row,
			.evaluate-subtasks-page .datatable .dt-scrollable .dt-row {
				width: max-content;
			}
		`;
		document.head.appendChild(style);
	}

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Evaluate SubTasks'),
		single_column: true,
	});

	$(wrapper).addClass('evaluate-subtasks-page');

	page.state = {
		rows: [],
		datatable: null,
	};

	const $main = $(page.body).empty();
	// const $toolbar = $(
	// 	`<div class="evaluate-subtasks-toolbar" style="display:flex; gap:12px; align-items:center; margin-bottom: 12px; flex-wrap: wrap;">
	// 		<div class="text-muted" data-role="hint"></div>
	// 	</div>`,
	// ).appendTo($main);

	const $table_area = $(
		`<div class="evaluate-subtasks-table" style="min-height: 200px;"></div>`,
	).appendTo($main);

	const search_field = page.add_field({
		label: __('Search'),
		fieldtype: 'Data',
		fieldname: 'txt',
		change: () => refresh(),
	});

	page.set_primary_action(__('Evaluate Selected'), () => evaluate_selected(), 'octicon octicon-check');
	page.add_action_item(__('Refresh'), () => refresh());

	$table_area.on('click', '[data-action="open-subtask"]', (e) => {
		e.preventDefault();
		const subtask = $(e.currentTarget).attr('data-subtask');
		if (!subtask) return;
		frappe.set_route('subtask', subtask);
	});

	$table_area.on('click', '[data-action="view-submission"]', (e) => {
		e.preventDefault();
		const subtask = $(e.currentTarget).attr('data-subtask');
		const row = (page.state.rows || []).find((r) => r.subtask === subtask);
		if (!row) return;
		show_submission_dialog(row);
	});

	async function refresh() {
		frappe.dom.freeze(__('Loading SubTasks...'));
		try {
			const txt = search_field?.get_value?.() || '';
			const r = await frappe.call({
				method: 'hrms.task_management.page.evaluate_subtasks.evaluate_subtasks.get_done_subtasks',
				args: { txt },
			});
			page.state.rows = (r.message || []).map((row) => ({
				...row,
				// Datatable `format()` sometimes receives `row` as an array.
				// Putting the subtask id into the cell value makes formatting reliable.
				submission: row.subtask,
			}));
			render_table();
		} finally {
			frappe.dom.unfreeze();
		}
	}

	function render_table() {
		const rows = page.state.rows || [];
		// $toolbar.find('[data-role="hint"]').text(
		// 	rows.length
		// 		? __('Showing {0} SubTasks (status: Done)', [rows.length])
		// 		: __('No eligible SubTasks found.'),
		// );

		const columns = [
			{
				name: 'pic_subtask_name',
				id: 'pic_subtask_name',
				content: __('PIC SubTask'),
				width: 140,
				editable: false,
				focusable: false
			},
			{
				name: 'subtask_title',
				id: 'subtask_title',
				content: __('SubTask Title'),
				width: 280,
				editable: false,
				focusable: false,
				format: (value, row, column, data) => {
					// frappe-datatable may pass `row` as an array; `data` is more reliable.
					const subtask_id = data?.subtask || row?.subtask;
					const label = frappe.utils.escape_html(value || subtask_id || '');
					if (!subtask_id) return label;
					return `<a href="#" data-action="open-subtask" data-subtask="${frappe.utils.escape_html(subtask_id)}">${label}</a>`;
				},
			},
			{
				name: 'task_title',
				id: 'task_title',
				content: __('Task Title'),
				width: 240,
				editable: false,
				focusable: false,
			},
			{
				name: 'maintask_title',
				id: 'maintask_title',
				content: __('MainTask Title'),
				width: 240,
				editable: false,
				focusable: false,
			},
			{
				name: 'value',
				id: 'value',
				content: __('Value'),
				width: 100,
				editable: false,
				focusable: false,
				align: 'left',
			},
			{
				name: 'priority',
				id: 'priority',
				content: __('Priority'),
				width: 110,
				editable: false,
				focusable: false,
			},
			{
				name: 'target_time_minutes',
				id: 'target_time_minutes',
				content: __('Target Time Minutes'),
				width: 180,
				editable: false,
				focusable: false,
			},
			{
				name: 'submission',
				id: 'submission',
				content: __('Submission'),
				width: 120,
				editable: false,
				focusable: false,
				format: (value) => {
					if (!value) return '';
					return `<a class="btn btn-xs btn-default" data-action="view-submission" data-subtask="${frappe.utils.escape_html(value)}">${__('View')}</a>`;
				},
			},
		].map((x) => ({ ...x, dropdown: true, align: x.align || 'left' }));
		// Enable sorting on all columns by default
		columns.forEach((c) => {
			if (typeof c.sortable === 'undefined') c.sortable = true;
		});

		const hide_remove_column = (dt) => {
			try {
				const list = dt?.columnmanager?.$dropdownList;
				// Default header dropdown items:
				// 0: Sort Ascending, 1: Sort Descending, 2: Reset sorting, 3: Remove column
				if (list?.children?.[3]) {
					list.children[3].classList.add('dt-hidden');
				}
			} catch (e) {
				// ignore
			}
		};

		const ensure_horizontal_scroll = (dt) => {
			try {
				if (dt?.bodyScrollable) {
					dt.bodyScrollable.style.overflowX = 'auto';
				}
			} catch (e) {
				// ignore
			}
		};

		if (page.state.datatable) {
			page.state.datatable.rowmanager.checkMap = [];
			page.state.datatable.options.noDataMessage = __('No Data');
			page.state.datatable.refresh(rows, columns);
			hide_remove_column(page.state.datatable);
			ensure_horizontal_scroll(page.state.datatable);
			return;
		}

		const $dt = $('<div class="datatable-wrapper"></div>').appendTo($table_area.empty());
		page.state.datatable = new frappe.DataTable($dt.get(0), {
			columns,
			data: rows,
			checkboxColumn: true,
			checkedRowStatus: false,
			serialNoColumn: false,
			dynamicRowHeight: true,
			inlineFilters: true,
			// 'fluid' layout can internally set overflowX:hidden during refresh.
			layout: 'fixed',
			cellHeight: 35,
			noDataMessage: __('No Data'),
			disableReorderColumn: true,
			events: {
				onCheckRow: () => { },
			},
		});
		hide_remove_column(page.state.datatable);
		ensure_horizontal_scroll(page.state.datatable);
	}

	function show_submission_dialog(row) {
		const d = new frappe.ui.Dialog({
			title: __('Submission'),
			size: 'large',
			fields: [
				{ fieldtype: 'HTML', fieldname: 'body' },
			],
			primary_action_label: __('Close'),
			primary_action: () => d.hide(),
		});

		const attachment = row.attachment ? frappe.urllib.get_full_url(row.attachment) : null;
		const attachment_html = attachment
			? `<a href="${attachment}" target="_blank" rel="noopener noreferrer">${__('Open Attachment')}</a>`
			: `<span class="text-muted">${__('No attachment')}</span>`;

		const submission_text = row.submission_text || '';
		const title = frappe.utils.escape_html(row.subtask_title || row.subtask || '');

		d.get_field('body').$wrapper.html(
			`<div>
				<div style="margin-bottom: 8px;"><b>${__('SubTask')}:</b> ${title}</div>
				<div style="margin-bottom: 8px;"><b>${__('Attachment')}:</b> ${attachment_html}</div>
				<hr style="margin: 12px 0;">
				<div><b>${__('Text')}:</b></div>
				<div class="frappe-card" style="padding: 12px; margin-top: 8px;">${submission_text || `<span class="text-muted">${__('No submission text')}</span>`}</div>
			</div>`,
		);
		d.show();
	}

	function get_selected_rows() {
		const dt = page.state.datatable;
		if (!dt) return [];
		const indexes = dt.rowmanager.getCheckedRows();
		return indexes.map((i) => page.state.rows[i]).filter((x) => x);
	}

	function evaluate_selected() {
		const selected = get_selected_rows();
		if (!selected.length) {
			frappe.msgprint(__('Please select at least one SubTask.'));
			return;
		}

		const parse_int = (value) => {
			if (value === null || typeof value === 'undefined') return NaN;
			const str = String(value).trim();
			if (!str) return NaN;
			const n = Number.parseInt(str, 10);
			return Number.isFinite(n) ? n : NaN;
		};

		const clamp_performance = (n) => {
			if (!Number.isFinite(n)) return { value: n, clamped: false };
			if (n < 1) return { value: 1, clamped: true };
			if (n > 120) return { value: 120, clamped: true };
			return { value: n, clamped: false };
		};

		const d = new frappe.ui.Dialog({
			title: __('Evaluate Selected SubTasks'),
			size: 'large',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'items_html',
				},
			],
			primary_action_label: __('Create Evaluations'),
			primary_action: async () => {
				const items = [];
				const invalid = [];
				d.$wrapper.find('tr[data-subtask]').each(function () {
					const subtask = $(this).attr('data-subtask');
					const title = $(this).attr('data-title') || subtask;
					const $input = $(this).find('input[data-field="performance"]');
					const raw = $input.val();
					const performance = parse_int(raw);

					if (!Number.isFinite(performance) || performance < 1 || performance > 120) {
						$input.addClass('is-invalid');
						invalid.push({ subtask, title, performance: raw });
						return;
					}

					$input.removeClass('is-invalid');
					items.push({ subtask, performance });
				});

				if (invalid.length) {
					frappe.msgprint({
						title: __('Invalid Performance'),
						indicator: 'red',
						message:
							`<div style="margin-bottom: 8px;">${__('Performance must be between 1 and 120.')}</div>` +
							'<ul>' +
							invalid
								.slice(0, 20)
								.map((x) => `<li><b>${frappe.utils.escape_html(x.title || x.subtask || '')}</b>: ${frappe.utils.escape_html(String(x.performance ?? ''))}</li>`)
								.join('') +
							'</ul>',
						is_minimizable: true,
					});
					return;
				}

				frappe.dom.freeze(__('Creating Evaluations...'));
				try {
					const r = await frappe.call({
						method: 'hrms.task_management.page.evaluate_subtasks.evaluate_subtasks.bulk_create_evaluations',
						args: { items },
					});
					const result = r.message || {};
					show_bulk_result(result);
					d.hide();
					await refresh();
				} finally {
					frappe.dom.unfreeze();
				}
			},
			secondary_action_label: __('Cancel'),
			secondary_action: () => d.hide(),
		});

		const rows_html = selected
			.map((r) => {
				const title = frappe.utils.escape_html(r.subtask_title || r.subtask);
				return `
					<tr data-subtask="${frappe.utils.escape_html(r.subtask)}" data-title="${title}">
						<td style="width: 70%;">${title}</td>
						<td style="width: 30%;">
							<input data-field="performance" type="number" class="form-control" min="1" max="120" step="1" required value="100" />
						</td>
					</tr>
				`;
			})
			.join('');

		d.get_field('items_html').$wrapper.html(
			`<div class="text-muted" style="margin-bottom: 10px;">
				${__('Set performance (1–120) for each SubTask.')}
			</div>
			<div class="text-danger" data-role="perf-warning" style="display:none; margin-bottom: 10px;"></div>
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__('SubTask')}</th>
						<th>${__('Performance')}</th>
					</tr>
				</thead>
				<tbody>${rows_html}</tbody>
			</table>`,
		);

		d.show();

		const show_perf_warning = (text) => {
			const $w = d.$wrapper.find('[data-role="perf-warning"]');
			if (!$w.length) return;
			$w.text(text).show();
			clearTimeout(d._perf_warn_timer);
			d._perf_warn_timer = setTimeout(() => $w.fadeOut(150), 2500);
		};

		// Clamp inputs to 1..120 on the fly and show a small warning when we adjust
		d.$wrapper.on('input', 'input[data-field="performance"]', function () {
			const $input = $(this);
			const raw = $input.val();
			const parsed = parse_int(raw);
			if (!Number.isFinite(parsed)) {
				$input.addClass('is-invalid');
				return;
			}
			const { value, clamped } = clamp_performance(parsed);
			$input.removeClass('is-invalid');
			if (clamped) {
				$input.val(value);
				show_perf_warning(__('Performance must be between 1 and 120. Value adjusted.'));
			}
		});

		// Also validate on blur/change (covers mousewheel and some browsers)
		d.$wrapper.on('change blur', 'input[data-field="performance"]', function () {
			const $input = $(this);
			const parsed = parse_int($input.val());
			if (!Number.isFinite(parsed)) {
				$input.addClass('is-invalid');
				return;
			}
			const { value, clamped } = clamp_performance(parsed);
			$input.removeClass('is-invalid');
			if (clamped) {
				$input.val(value);
				show_perf_warning(__('Performance must be between 1 and 120. Value adjusted.'));
			}
		});
	}

	function show_bulk_result(result) {
		const success = result.success || [];
		const failure = result.failure || [];

		let message = '';
		let indicator = 'green';
		let title = __('Success');

		let success_html = '';
		let failure_html = '';

		if (failure.length) {
			indicator = success.length ? 'orange' : 'red';
			title = success.length ? __('Partial Success') : __('Failure');
			failure_html += `<div style="margin-bottom: 10px;"><b>${__('Failed')}:</b> ${failure.length}</div>`;
			failure_html += `<ul>` + failure
				.slice(0, 20)
				.map((f) => `<li><b>${frappe.utils.escape_html(f.subtask_title || '')}</b>: ${frappe.utils.escape_html(f.error || '')}</li>`)
				.join('') + `</ul>`;
			if (failure.length > 20) {
				failure_html += `<div class="text-muted">${__('Only showing first 20 failures.')}</div>`;
			}
		}

		if (success.length) {
			const evaluation_owner_route = "/app/evaluation/?owner=" + encodeURIComponent(frappe.session.user);
			success_html += `<div style="margin-bottom: 10px;"><b>${__('Created')}:</b> ${success.length} ${__('evaluations')}</div>`;
			success_html += `<ul>` + success
				.slice(0, 20)
				.map((s) => {
					const title = frappe.utils.escape_html(s.subtask_title || s.subtask || '');
					const evaluation_name = s.evaluation || '';
					const evaluation_label = frappe.utils.escape_html(evaluation_name);
					const evaluation_href = evaluation_name
						? ("/app/evaluation/" + encodeURIComponent(evaluation_name))
						: '';
					const evaluation_link = evaluation_href
						? `<a href="${evaluation_href}">${evaluation_label}</a>`
						: `<span class="text-muted">${__('(no evaluation id)')}</span>`;
					return `<li><b>${title}</b>: ${evaluation_link}</li>`;
				})
				.join('') + `</ul>`;
			success_html += `<a href="${evaluation_owner_route}"><b>${__('Evaluations')}</b></a> ${__('created from Evaluated SubTasks.')}`;
		}

		if (success_html && failure_html) {
			message = `${success_html}<hr style="margin: 12px 0;">${failure_html}`;
		} else {
			message = success_html || failure_html;
		}

		frappe.msgprint({
			title,
			indicator,
			message: message || __('Done.'),
			is_minimizable: true,
		});
	}

	refresh();
}