frappe.listview_settings['Evaluation'] = {
	add_fields: ['subtask', 'subtask_name', 'pic_subtask', 'pic_subtask_name'],

	formatters: {
		subtask(val, df, doc) {
			return doc.subtask_name || val;
		}, pic_subtask(val, df, doc) {
			return doc.pic_subtask_name || val;
		}
	},

	refresh(listview) {
		let workspace = 'Task Management';

		frappe.breadcrumbs.all[frappe.get_route_str()] = {
			workspace: workspace,
			type: 'List'
		};
		frappe.breadcrumbs.update();

		const applySubjectWrap = () => {
			document.querySelectorAll('.list-row-container .list-subject').forEach(function(col){
				// sizing
				// col.style.maxWidth = "25vw";
				// col.style.minWidth = "25vw";
				// wrapping
				col.classList.remove('ellipsis');
				col.style.whiteSpace = 'normal';
				col.style.overflow = 'visible';
				col.style.textOverflow = 'initial';
				// level container aligns center by default; align to start so multi-lines look OK
				col.style.alignItems = 'center';

				// remove ellipsis from parent left column (if any)
				const left = col.closest('.level-left');
				if (left) left.classList.remove('ellipsis');

				// ensure inner level-item can shrink/wrap
				col.querySelectorAll('.level-item').forEach(item => {
					item.style.minWidth = '0';
					item.style.maxWidth = '100%';
					item.style.justifyContent = 'flex-start';
					// let text take available width
					if (!item.classList.contains('select-like')) {
						item.style.flex = '1 1 auto';
					}
					item.classList.remove('ellipsis');
				});

				// remove ellipsis on inner wrappers/anchor so text can wrap
				const bold = col.querySelector('.bold');
				if (bold) bold.classList.remove('ellipsis');
				const a = col.querySelector('a.ellipsis, a');
				if (a) {
					a.classList.remove('ellipsis');
					// apply 2-line clamp with ellipsis
					if (!document.getElementById('subtask-multiline-clamp-style')) {
						const style = document.createElement('style');
						style.id = 'subtask-multiline-clamp-style';
						style.textContent = `
							.subtask-title-clamp {\n								display: -webkit-box;\n								-webkit-line-clamp: 2;\n								-webkit-box-orient: vertical;\n								overflow: hidden;\n								text-overflow: ellipsis;\n								white-space: normal !important;\n								word-break: break-word;\n							}
						`;
						document.head.appendChild(style);
					}
					a.classList.add('subtask-title-clamp');
				}
			})
		};
		// run after rows are appended
		requestAnimationFrame(applySubjectWrap);
		setTimeout(applySubjectWrap, 0);
		setTimeout(applySubjectWrap, 50);
	},
};
