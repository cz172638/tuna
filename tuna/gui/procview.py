import pygtk
pygtk.require("2.0")

from tuna import tuna, gui
import gobject, gtk, procfs, re, schedutils
try:
	import perf
except:
	pass

def N_(s):
	"""gettext_noop"""
	return s

class process_druid:

	( PROCESS_COL_PID, PROCESS_COL_NAME ) = range(2)

	def __init__(self, ps, pid, pid_info, nr_cpus, gladefile):
		self.ps = ps
		self.pid = pid
		self.pid_info = pid_info
		self.nr_cpus = nr_cpus
		self.window = gtk.glade.XML(gladefile, "set_process_attributes", "tuna")
		self.dialog = self.window.get_widget("set_process_attributes")
		pixbuf = self.dialog.render_icon(gtk.STOCK_PREFERENCES,
						 gtk.ICON_SIZE_SMALL_TOOLBAR)
		self.dialog.set_icon(pixbuf)
		event_handlers = { "on_cmdline_regex_changed" : self.on_cmdline_regex_changed,
				   "on_affinity_text_changed" : self.on_affinity_text_changed,
				   "on_sched_policy_combo_changed" : self.on_sched_policy_combo_changed,
				   "on_command_regex_clicked" : self.on_command_regex_clicked,
				   "on_all_these_threads_clicked" : self.on_all_these_threads_clicked,
				   "on_just_this_thread_clicked" : self.on_just_this_thread_clicked }
		self.window.signal_autoconnect(event_handlers)

		self.sched_pri = self.window.get_widget("sched_pri_spin")
		self.sched_policy = self.window.get_widget("sched_policy_combo")
		self.regex_edit = self.window.get_widget("cmdline_regex")
		self.affinity = self.window.get_widget("affinity_text")
		self.just_this_thread = self.window.get_widget("just_this_thread")
		self.all_these_threads = self.window.get_widget("all_these_threads")
		processes = self.window.get_widget("matching_process_list")

		self.sched_pri.set_value(int(pid_info["stat"]["rt_priority"]))
		cmdline_regex = procfs.process_cmdline(pid_info)
		self.affinity_text = tuna.list_to_cpustring(schedutils.get_affinity(pid))
		self.affinity.set_text(self.affinity_text)
		self.create_matching_process_model(processes)
		self.create_policy_model(self.sched_policy)
		self.sched_policy.set_active(schedutils.get_scheduler(pid))
		self.regex_edit.set_text(cmdline_regex)
		self.just_this_thread.set_active(True)
		self.regex_edit.set_sensitive(False)
		if not ps.has_key(pid) or not ps[pid].has_key("threads"):
			self.all_these_threads.hide()
		self.on_just_this_thread_clicked(None)

	def refresh_match_pids(self, cmdline_regex):
		self.process_list_store.clear()
		for match_pid in self.ps.find_by_cmdline_regex(cmdline_regex):
			info = self.process_list_store.append()
			pid_info = self.ps[match_pid]
			cmdline = procfs.process_cmdline(pid_info)
			self.process_list_store.set(info, self.PROCESS_COL_PID, match_pid,
						    self.PROCESS_COL_NAME,
						    cmdline)

	def create_matching_process_model(self, processes):
		labels = [ "PID", "Name" ]

		self.process_list_store = gtk.ListStore(gobject.TYPE_UINT,
							gobject.TYPE_STRING)
		renderer = gtk.CellRendererText()

		for col in range(len(labels)):
			column = gtk.TreeViewColumn(labels[col], renderer, text = col)
			column.set_sort_column_id(col)
			processes.append_column(column)

		processes.set_model(self.process_list_store)

	def create_policy_model(self, policy):
		( COL_TEXT, COL_SCHED ) = range(2)
		list_store = gtk.ListStore(gobject.TYPE_STRING,
					   gobject.TYPE_UINT)
		renderer = gtk.CellRendererText()
		policy.pack_start(renderer, True)
		policy.add_attribute(renderer, "text", COL_TEXT)
		for pol in range(4):
			row = list_store.append()
			list_store.set(row, COL_TEXT, schedutils.schedstr(pol),
					    COL_SCHED, pol)
		policy.set_model(list_store)

	def on_cmdline_regex_changed(self, entry):
		process_regex_text = entry.get_text()
		try:
			cmdline_regex = re.compile(process_regex_text)
		except:
			self.process_list_store.clear()
			return
		self.refresh_match_pids(cmdline_regex)

	def on_just_this_thread_clicked(self, button):
		self.regex_edit.set_sensitive(False)
		self.process_list_store.clear()
		info = self.process_list_store.append()
		cmdline = procfs.process_cmdline(self.pid_info)
		self.process_list_store.set(info,
					    self.PROCESS_COL_PID, self.pid,
					    self.PROCESS_COL_NAME, cmdline)

	def on_command_regex_clicked(self, button):
		self.regex_edit.set_sensitive(True)
		self.on_cmdline_regex_changed(self.regex_edit)

	def on_all_these_threads_clicked(self, button):
		self.regex_edit.set_sensitive(False)
		self.process_list_store.clear()
		info = self.process_list_store.append()
		cmdline = procfs.process_cmdline(self.ps[self.pid])
		self.process_list_store.set(info,
					    self.PROCESS_COL_PID, self.pid,
					    self.PROCESS_COL_NAME, cmdline)
		for tid in self.ps[self.pid]["threads"].keys():
			child = self.process_list_store.append()
			self.process_list_store.set(child,
						    self.PROCESS_COL_PID, tid,
						    self.PROCESS_COL_NAME, cmdline)


	def on_sched_policy_combo_changed(self, button):
		new_policy = self.sched_policy.get_active()
		if new_policy in ( schedutils.SCHED_FIFO, schedutils.SCHED_RR ):
			can_change_pri = True
		else:
			can_change_pri = False
		self.sched_pri.set_sensitive(can_change_pri)

	def on_affinity_text_changed(self, button):
		gui.on_affinity_text_changed(self)

	def set_attributes_for_regex(self, regex, new_policy, new_prio, new_affinity):
		changed = False
		cmdline_regex = re.compile(regex)
		for match_pid in self.ps.find_by_cmdline_regex(cmdline_regex):
			if gui.thread_set_attributes(self.ps[match_pid],
						     new_policy, new_prio,
						     new_affinity,
						     self.nr_cpus):
				changed = True

		return changed

	def set_attributes_for_threads(self, pid, new_policy, new_prio, new_affinity):
		changed = False
		threads = self.ps[pid]["threads"]
		for tid in threads.keys():
			if gui.thread_set_attributes(threads[tid], new_policy,
						     new_prio, new_affinity,
						     self.nr_cpus):
				changed = True

		return changed

	def run(self):
		changed = False
		if self.dialog.run() == gtk.RESPONSE_OK:
			new_policy = int(self.sched_policy.get_active())
			new_prio = int(self.sched_pri.get_value())
			new_affinity = self.affinity.get_text()
			if self.just_this_thread.get_active():
				changed = gui.thread_set_attributes(self.pid_info,
								    new_policy,
								    new_prio,
								    new_affinity,
								    self.nr_cpus)
			elif self.all_these_threads.get_active():
				if gui.thread_set_attributes(self.pid_info,
							     new_policy, new_prio,
							     new_affinity,
							     self.nr_cpus):
					changed = True
				if self.set_attributes_for_threads(self.pid,
								   new_policy,
								   new_prio,
								   new_affinity):
					changed = True
			else:
				changed = self.set_attributes_for_regex(self.regex_edit.get_text(),
									new_policy,
									new_prio,
									new_affinity)

		self.dialog.destroy()
		return changed

class procview:

	nr_columns = 8
	( COL_PID, COL_POL, COL_PRI, COL_AFF, COL_VOLCTXT, COL_NONVOLCTXT, COL_CGROUP, COL_CMDLINE ) = range(nr_columns)
	columns = (gui.list_store_column(_("PID")),
		   gui.list_store_column(_("Policy"), gobject.TYPE_STRING),
		   gui.list_store_column(_("Priority")),
		   gui.list_store_column(_("Affinity"), gobject.TYPE_STRING),
		   gui.list_store_column(_("VolCtxtSwitch"), gobject.TYPE_UINT),
		   gui.list_store_column(_("NonVolCtxtSwitch"), gobject.TYPE_UINT),
		   gui.list_store_column(_("CGroup"), gobject.TYPE_STRING),
		   gui.list_store_column(_("Command Line"), gobject.TYPE_STRING))

	def __init__(self, treeview, ps,
		     show_kthreads, show_uthreads,
		     cpus_filtered, gladefile):
		self.ps = ps
		self.treeview = treeview
		self.nr_cpus = procfs.cpuinfo().nr_cpus
		self.gladefile = gladefile
	
		self.evlist = None
		try:
			self.perf_init() 
		except: # No perf, poll /proc baby, poll
			pass

		if not ps[1]["status"].has_key("voluntary_ctxt_switches"):
			self.nr_columns = 5
		else:
			self.nr_columns = 7
		try:
			if ps[1]["cgroups"]:
				self.nr_columns = self.nr_columns + 1
		except:
			pass

		self.columns = (gui.list_store_column(_("PID")),
						gui.list_store_column(_("Policy"), gobject.TYPE_STRING),
						gui.list_store_column(_("Priority")),
						gui.list_store_column(_("Affinity"), gobject.TYPE_STRING))

		if self.nr_columns==5:
			( self.COL_PID, self.COL_POL, self.COL_PRI, self.COL_AFF, self.COL_CMDLINE ) = range(self.nr_columns)
			self.columns = self.columns + (gui.list_store_column(_("Command Line"), gobject.TYPE_STRING))

		elif self.nr_columns==6:
			( self.COL_PID, self.COL_POL, self.COL_PRI, self.COL_AFF, self.COL_CGROUP, self.COL_CMDLINE ) = range(self.nr_columns)
			self.columns = self.columns + (gui.list_store_column(_("CGroup"), gobject.TYPE_STRING),
										   gui.list_store_column(_("Command Line"), gobject.TYPE_STRING))

		elif self.nr_columns==7:
			( self.COL_PID, self.COL_POL, self.COL_PRI, self.COL_AFF, self.COL_VOLCTXT,
				self.NONVOLCTXT, self.COL_CMDLINE ) = range(self.nr_columns)
			self.columns = self.columns + (gui.list_store_column(_("VolCtxtSwitch"), gobject.TYPE_UINT),
										   gui.list_store_column(_("NonVolCtxtSwitch"), gobject.TYPE_UINT),
										   gui.list_store_column(_("Command Line"), gobject.TYPE_STRING))

		elif self.nr_columns==8:
			( self.COL_PID, self.COL_POL, self.COL_PRI, self.COL_AFF, self.COL_VOLCTXT,
				self.COL_NONVOLCTXT, self.COL_CGROUP, self.COL_CMDLINE ) = range(self.nr_columns)
			self.columns = self.columns + (gui.list_store_column(_("VolCtxtSwitch"), gobject.TYPE_UINT),
										   gui.list_store_column(_("NonVolCtxtSwitch"), gobject.TYPE_UINT),
										   gui.list_store_column(_("CGroup"), gobject.TYPE_STRING),
										   gui.list_store_column(_("Command Line"), gobject.TYPE_STRING))

		self.tree_store = gtk.TreeStore(*gui.generate_list_store_columns_with_attr(self.columns))
		self.treeview.set_model(self.tree_store)

		# Allow selecting multiple rows
		selection = treeview.get_selection()
		selection.set_mode(gtk.SELECTION_MULTIPLE)

		# Allow enable drag and drop of rows
		self.treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
						       gui.DND_TARGETS,
						       gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
		self.treeview.connect("drag_data_get", self.on_drag_data_get_data)
		try:
			self.treeview.connect("query-tooltip", self.on_query_tooltip)
		except:
			# old versions of pygtk2+ doesn't have this signal
			pass

		self.renderer = gtk.CellRendererText()
		for col in range(self.nr_columns):
			column = gtk.TreeViewColumn(self.columns[col].name,
						    self.renderer, text = col)
			column.add_attribute(self.renderer, "weight",
					     col + self.nr_columns)
			column.set_sort_column_id(col)
			if(col == self.COL_CGROUP):
				column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
				column.set_fixed_width(130)
			try:
				self.treeview.set_tooltip_column(col)
			except:
				# old versions of pygtk2+ doesn't have this signal
				pass
			column.set_resizable(True)
			self.treeview.append_column(column)

		self.show_kthreads = show_kthreads
		self.show_uthreads = show_uthreads
		self.cpus_filtered = cpus_filtered
		self.refreshing = True

	def perf_process_events(self, source, condition):
		had_events = True
		while had_events:
			had_events = False
			for cpu in self.cpu_map:
				event = self.evlist.read_on_cpu(cpu)
				if event:
					had_events = True
					if event.type == perf.RECORD_FORK:
						if event.pid == event.tid:
							try:
								self.ps.processes[event.pid] = procfs.process(event.pid)
							except: # short lived thread
								pass
						else:
							try:
								self.ps.processes[event.pid].threads.processes[event.tid] = procfs.process(event.tid)
							except AttributeError:
								self.ps.processes[event.pid].threads = procfs.pidstats("/proc/%d/task/" % event.pid)
					elif event.type == perf.RECORD_EXIT:
						del self.ps[int(event.tid)]
					elif event.type == perf.RECORD_SAMPLE:
						tid = event.sample_tid
						if self.perf_counter.has_key(tid):
							self.perf_counter[tid] += event.sample_period
						else:
							self.perf_counter[tid] = event.sample_period
			
		self.show()
		return True

	def perf_init(self):
		self.cpu_map = perf.cpu_map()
		self.thread_map = perf.thread_map()
		self.evsel_cycles = perf.evsel(task = 1, comm = 1,
					       wakeup_events = 1,
					       watermark = 1,
					       sample_type = perf.SAMPLE_CPU |
							     perf.SAMPLE_TID)
		self.evsel_cycles.open(cpus = self.cpu_map, threads = self.thread_map);
		self.evlist = perf.evlist(self.cpu_map, self.thread_map)
		self.evlist.add(self.evsel_cycles)
		self.evlist.mmap()
		self.pollfd = self.evlist.get_pollfd()
		for f in self.pollfd:
			gobject.io_add_watch(f, gtk.gdk.INPUT_READ, self.perf_process_events)
		self.perf_counter = {}

	def on_query_tooltip(self, treeview, x, y, keyboard_mode, tooltip):
		x, y = treeview.convert_widget_to_bin_window_coords(x, y)
		ret = treeview.get_path_at_pos(x, y)
		tooltip.set_text(None)
		if not ret:
			return True
		path, col, xpos, ypos = ret
		if not path:
			return True
		col_id = col.get_sort_column_id()
		if col_id != self.COL_CMDLINE:
			return True
		row = self.tree_store.get_iter(path)
		if not row:
			return True
		pid = int(self.tree_store.get_value(row, self.COL_PID))
		if not tuna.iskthread(pid):
			return True
		cmdline = self.tree_store.get_value(row, self.COL_CMDLINE).split(' ')[0]
		help = tuna.kthread_help(cmdline)
		tooltip.set_markup("<b>%s %d(%s)</b>\n%s" % \
			(_("Kernel Thread"), pid, cmdline, _(help)))
		return True

	def foreach_selected_cb(self, model, path, iter, pid_list):
		pid = model.get_value(iter, self.COL_PID)
		pid_list.append(str(pid))

	def on_drag_data_get_data(self, treeview, context,
			          selection, target_id, etime):
		treeselection = treeview.get_selection()
		pid_list = []
		treeselection.selected_foreach(self.foreach_selected_cb, pid_list)
		selection.set(selection.target, 8, "pid:" + ",".join(pid_list))

	def set_thread_columns(self, iter, tid, thread_info):
		new_value = [ None ] * self.nr_columns

		new_value[self.COL_PRI] = int(thread_info["stat"]["rt_priority"])
		new_value[self.COL_POL] = schedutils.schedstr(schedutils.get_scheduler(tid))[6:]
		thread_affinity_list = schedutils.get_affinity(tid)

		new_value[self.COL_PID] = tid
		new_value[self.COL_AFF] = tuna.list_to_cpustring(thread_affinity_list)
		try:
			new_value[self.COL_VOLCTXT] = int(thread_info["status"]["voluntary_ctxt_switches"])
			new_value[self.COL_NONVOLCTXT] = int(thread_info["status"]["nonvoluntary_ctxt_switches"])
			new_value[self.COL_CGROUP] = thread_info["cgroups"]
		except:
			pass

		new_value[self.COL_CMDLINE] = procfs.process_cmdline(thread_info)

		gui.set_store_columns(self.tree_store, iter, new_value)

	def show(self, force_refresh = False):
		# Start with the first row, if there is one, on the
		# process list. If the first time update_rows will just
		# have everything in new_tids and append_new_tids will
		# create the rows.
		if not self.refreshing and not force_refresh:
			return
		row = self.tree_store.get_iter_first()
		self.update_rows(self.ps, row, None)
		self.treeview.show_all()

	def update_rows(self, threads, row, parent_row):
		new_tids = threads.keys()
		previous_row = None
		while row:
			tid = self.tree_store.get_value(row, self.COL_PID)
			if previous_row:
				previous_tid = self.tree_store.get_value(previous_row, self.COL_PID)
				if previous_tid == tid:
					# print "WARNING: tree_store dup %d, fixing..." % tid
					self.tree_store.remove(previous_row)
			if not threads.has_key(tid):
				if self.tree_store.remove(row):
					# removed and now row is the next one
					continue
				# removed and its the last one
				break
			else:
				try:
					new_tids.remove(tid)
				except:
					# FIXME: understand in what situation this
					# can happen, seems harmless from visual
					# inspection.
					pass
				if tuna.thread_filtered(tid, self.cpus_filtered,
						        self.show_kthreads,
							self.show_uthreads):
					if self.tree_store.remove(row):
						# removed and now row is the next one
						continue
					# removed and its the last one
					break
				else:
					try:
						self.set_thread_columns(row, tid, threads[tid])

						if threads[tid].has_key("threads"):
							children = threads[tid]["threads"]
						else:
							children = {}

						child_row = self.tree_store.iter_children(row)
						self.update_rows(children, child_row, row)
					except: # thread doesn't exists anymore
						if self.tree_store.remove(row):
							# removed and now row is the next one
							continue
						# removed and its the last one
						break

			previous_row = row
			row = self.tree_store.iter_next(row)

		new_tids.sort()
		self.append_new_tids(parent_row, threads, new_tids)

	def append_new_tids(self, parent_row, threads, tid_list):
		for tid in tid_list:
			if tuna.thread_filtered(tid, self.cpus_filtered,
						self.show_kthreads,
						self.show_uthreads):
				continue

			row = self.tree_store.append(parent_row)

			try:
				self.set_thread_columns(row, tid, threads[tid])
			except: # Thread doesn't exists anymore
				self.tree_store.remove(row)
				continue

			if threads[tid].has_key("threads"):
				children = threads[tid]["threads"]
				children_list = children.keys()
				children_list.sort()
				for child in children_list:
					child_row = self.tree_store.append(row)
					try:
						self.set_thread_columns(child_row,
									child,
									children[child])
					except: # Thread doesn't exists anymore
						self.tree_store.remove(child_row)

	def refresh(self):
		self.ps.reload()
		self.ps.reload_threads()

		self.show(True)

	def edit_attributes(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.tree_store.get_iter(path)
		pid = self.tree_store.get_value(row, self.COL_PID)
		if self.ps.has_key(pid):
			pid_info = self.ps[pid]
		else:
			parent = self.tree_store.iter_parent(row)
			ppid = self.tree_store.get_value(parent, self.COL_PID)
			pid_info = self.ps[ppid].threads[pid]

		dialog = process_druid(self.ps, pid, pid_info, self.nr_cpus,
				       self.gladefile)
		if dialog.run():
			self.refresh()

	def kthreads_view_toggled(self, a):
		self.show_kthreads = not self.show_kthreads
		self.show(True)

	def uthreads_view_toggled(self, a):
		self.show_uthreads = not self.show_uthreads
		self.show(True)

	def help_dialog(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.tree_store.get_iter(path)
		pid = self.tree_store.get_value(row, self.COL_PID)
		if not self.ps.has_key(pid):
			return

		cmdline = self.tree_store.get_value(row, self.COL_CMDLINE)
		help, title = tuna.kthread_help_plain_text(pid, cmdline)

		dialog = gtk.MessageDialog(None,
					   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					   gtk.MESSAGE_INFO,
					   gtk.BUTTONS_OK, _(help))
		dialog.set_title(title)
		ret = dialog.run()
		dialog.destroy()

	def refresh_toggle(self, a):
		self.refreshing = not self.refreshing

	def save_kthreads_tunings(self, a):
		dialog = gtk.FileChooserDialog(_("Save As"),
					       None,
					       gtk.FILE_CHOOSER_ACTION_SAVE,
					       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
						gtk.STOCK_OK, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)

		try:
			dialog.set_do_overwrite_confirmation(True)
		except:
			pass

		filter = gtk.FileFilter()
		filter.set_name("rtctl config files")
		filter.add_pattern("*.rtctl")
		filter.add_pattern("*.tuna")
		filter.add_pattern("*rtgroup*")
		dialog.add_filter(filter)

		filter = gtk.FileFilter()
		filter.set_name("All files")
		filter.add_pattern("*")
		dialog.add_filter(filter)

		response = dialog.run()

		filename = dialog.get_filename()
		dialog.destroy()

		if response != gtk.RESPONSE_OK:
			return

		self.refresh()
		kthreads = tuna.get_kthread_sched_tunings(self.ps)
		tuna.generate_rtgroups(filename, kthreads, self.nr_cpus)

		if filename != "/etc/rtgroups":
			dialog = gtk.MessageDialog(None,
						   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						   gtk.MESSAGE_INFO,
						   gtk.BUTTONS_YES_NO,
						   "Kernel thread tunings saved!\n\n"
						   "Now you can use it with rtctl:\n\n"
						   "rtctl --file %s reset\n\n"
						   "If you want the changes to be in "
						   "effect every time you boot the system "
						   "please move %s to /etc/rtgroups\n\n"
						   "Do you want to do that now?" % (filename, filename))
			response = dialog.run()
			dialog.destroy()
			if response == gtk.RESPONSE_YES:
				filename = "/etc/rtgroups"
				tuna.generate_rtgroups(filename, kthreads, self.nr_cpus)

		dialog = gtk.MessageDialog(None,
					   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					   gtk.MESSAGE_INFO,
					   gtk.BUTTONS_OK,
					   _("Kernel thread tunings saved to %s!") % filename)
		dialog.run()
		dialog.destroy()

	def on_processlist_button_press_event(self, treeview, event):
		if event.type != gtk.gdk.BUTTON_PRESS or event.button != 3:
			return

		self.last_x = int(event.x)
		self.last_y = int(event.y)

		menu = gtk.Menu()

		setattr = gtk.MenuItem(_("_Set process attributes"))
		if self.refreshing:
			refresh = gtk.MenuItem(_("Sto_p refreshing the process list"))
		else:
			refresh = gtk.MenuItem(_("_Refresh the process list"))

		if self.show_kthreads:
			kthreads = gtk.MenuItem(_("_Hide kernel threads"))
		else:
			kthreads = gtk.MenuItem(_("_Show kernel threads"))

		if self.show_uthreads:
			uthreads = gtk.MenuItem(_("_Hide user threads"))
		else:
			uthreads = gtk.MenuItem(_("_Show user threads"))

		help = gtk.MenuItem(_("_What is this?"))

		save_kthreads_tunings = gtk.MenuItem(_("_Save kthreads tunings"))

		menu.add(save_kthreads_tunings)
		menu.add(setattr)
		menu.add(refresh)
		menu.add(kthreads)
		menu.add(uthreads)
		menu.add(help)

		save_kthreads_tunings.connect_object('activate',
						     self.save_kthreads_tunings, event)
		setattr.connect_object('activate', self.edit_attributes, event)
		refresh.connect_object('activate', self.refresh_toggle, event)
		kthreads.connect_object('activate', self.kthreads_view_toggled, event)
		uthreads.connect_object('activate', self.uthreads_view_toggled, event)
		help.connect_object('activate', self.help_dialog, event)

		save_kthreads_tunings.show()
		setattr.show()
		refresh.show()
		kthreads.show()
		uthreads.show()
		help.show()

		menu.popup(None, None, None, event.button, event.time)

	def toggle_mask_cpu(self, cpu, enabled):
		if not enabled:
			if cpu not in self.cpus_filtered:
				self.cpus_filtered.append(cpu)
				self.show(True)
		else:
			if cpu in self.cpus_filtered:
				self.cpus_filtered.remove(cpu)
				self.show(True)
