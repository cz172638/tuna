#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import pygtk
pygtk.require("2.0")

import copy, ethtool, gtk, gobject, os, pango, procfs, re, schedutils, sys, tuna
import gtk.glade

try:
	from sets import Set as set
except:
	# OK, we're modern, having sets as first class citizens
	pass

# FIXME: should go to python-schedutils
( SCHED_OTHER, SCHED_FIFO, SCHED_RR, SCHED_BATCH ) = range(4)

DND_TARGET_STRING = 0
DND_TARGET_ROOTWIN = 1

DND_TARGETS = [ ('STRING', 0, DND_TARGET_STRING),
		('text/plain', 0, DND_TARGET_STRING),
		('application/x-rootwin-drop', 0, DND_TARGET_ROOTWIN) ]

tuna_glade_dirs = [ ".", "tuna", "/usr/share/tuna" ]
tuna_glade = None

def set_affinity_warning(tid, affinity):
	dialog = gtk.MessageDialog(None,
				   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				   gtk.MESSAGE_WARNING,
				   gtk.BUTTONS_OK,
				   "Couldn't change the affinity of %d to %s!" % \
				   (tid, affinity))
	dialog.run()
	dialog.destroy()

def drop_handler_move_threads_to_cpu(cpu, data):
	pid_list = [ int(pid) for pid in data.split(",") ]
	if cpu >= 0:
		new_affinity = [ cpu, ]
	else:
		new_affinity = range(-cpu)

	tuna.move_threads_to_cpu(new_affinity, pid_list)

def drop_handler_move_irqs_to_cpu(cpu, data):
	irq_list = [ int(irq) for irq in data.split(",") ]
	if cpu >= 0:
		new_affinity = [ 1 << cpu, ]
	else:
		cpu = -cpu
		new_affinity = [ (1 << cpu) - 1, ]
	
	for irq in irq_list:
		tuna.set_irq_affinity(irq, new_affinity)

	# FIXME: check if we really changed the affinity, but
	# its only an optimization to avoid a needless refresh
	# in the irqview, now we always refresh.
	return True

def set_store_columns(store, row, new_value):
	nr_columns = len(new_value)
	for col in range(nr_columns):
		col_weight = col + nr_columns
		cur_value = store.get_value(row, col)
		if cur_value == new_value[col]:
			new_weight = pango.WEIGHT_NORMAL
		else:
			new_weight = pango.WEIGHT_BOLD

		store.set(row, col, new_value[col], col_weight, new_weight)

class list_store_column:
	def __init__(self, name, type = gobject.TYPE_UINT):
		self.name = name
		self.type = type

def generate_list_store_columns_with_attr(columns):
	for column in columns:
		yield column.type
	for column in columns:
		yield gobject.TYPE_UINT

class cpuview:

	( COL_FILTER, COL_CPU, COL_USAGE ) = range(3)

	def __init__(self, treeview, procview, irqview, cpus_filtered):
		self.cpustats = procfs.cpusstats()
		self.procview = procview
		self.irqview = irqview
		self.treeview = treeview
		self.list_store = gtk.ListStore(gobject.TYPE_BOOLEAN,
						gobject.TYPE_UINT,
						gobject.TYPE_UINT)
		self.treeview.set_model(self.list_store)
		self.nr_cpus = len(self.cpustats) - 1
		
		model = self.treeview.get_model()

		# Filter column
		renderer = gtk.CellRendererToggle()
		renderer.connect('toggled', self.filter_toggled, model)
		column = gtk.TreeViewColumn('Filter', renderer, active = self.COL_FILTER)
		self.treeview.append_column(column)

		# CPU# column
		column = gtk.TreeViewColumn('CPU', gtk.CellRendererText(),
					    text = self.COL_CPU)
		self.treeview.append_column(column)

		# CPU usage column
		try:
			column = gtk.TreeViewColumn('Usage', gtk.CellRendererProgress(),
						    text = self.COL_USAGE, value = self.COL_USAGE)
		except:
			# CellRendererProgress needs pygtk2 >= 2.6
			column = gtk.TreeViewColumn('Usage', gtk.CellRendererText(),
						    text = self.COL_USAGE)
		self.treeview.append_column(column)

		self.treeview.enable_model_drag_dest(DND_TARGETS,
						     gtk.gdk.ACTION_DEFAULT)
		self.treeview.connect("drag_data_received",
		 		       self.on_drag_data_received_data)

		self.timer = gobject.timeout_add(3000, self.refresh)

		self.drop_handlers = { "pid": (drop_handler_move_threads_to_cpu, self.procview),
				       "irq": (drop_handler_move_irqs_to_cpu, self.irqview), }

		self.previous_pid_affinities = None
		self.previous_irq_affinities = None
		self.cpus_filtered = cpus_filtered

	def isolate_cpu(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.list_store.get_iter(path)
		cpu = self.list_store.get_value(row, self.COL_CPU)
		self.previous_pid_affinities, \
		  self.previous_irq_affinities = tuna.isolate_cpus([cpu,], self.nr_cpus)

		if self.previous_pid_affinities:
			self.procview.refresh()

		if self.previous_irq_affinities:
			self.irqview.refresh()

	def include_cpu(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.list_store.get_iter(path)
		cpu = self.list_store.get_value(row, self.COL_CPU)
		self.previous_pid_affinities, \
		  self.previous_irq_affinities = tuna.include_cpu(cpu, self.nr_cpus)

		if self.previous_pid_affinities:
			self.procview.refresh()

		if self.previous_irq_affinities:
			self.irqview.refresh()

	def restore_cpu(self, a):
		if not (self.previous_pid_affinities or \
			self.previous_irq_affinities):
			return
		affinities = self.previous_pid_affinities
		for pid in affinities.keys():
			try:
				schedutils.set_affinity(pid, affinities[pid])
			except:
				pass

		affinities = self.previous_irq_affinities
		for irq in affinities.keys():
			tuna.set_irq_affinity(int(irq),
					      procfs.hexbitmask(affinities[irq],
								self.nr_cpus))
			
		self.previous_pid_affinities = None
		self.previous_irq_affinities = None

	def on_cpuview_button_press_event(self, treeview, event):
		if event.type != gtk.gdk.BUTTON_PRESS or event.button != 3:
			return

		self.last_x = int(event.x)
		self.last_y = int(event.y)

		menu = gtk.Menu()

		include = gtk.MenuItem("I_nclude CPU")
		isolate = gtk.MenuItem("_Isolate CPU")
		restore = gtk.MenuItem("_Restore CPU")

		menu.add(include)
		menu.add(isolate)
		menu.add(restore)

		include.connect_object('activate', self.include_cpu, event)
		isolate.connect_object('activate', self.isolate_cpu, event)
		if not (self.previous_pid_affinities or \
			self.previous_irq_affinities):
			restore.set_sensitive(False)
		restore.connect_object('activate', self.restore_cpu, event)

		include.show()
		isolate.show()
		restore.show()

		menu.popup(None, None, None, event.button, event.time)

	def on_drag_data_received_data(self, treeview, context, x, y,
				       selection, info, etime):
		drop_info = treeview.get_dest_row_at_pos(x, y)

		# pid list, a irq list, etc
		source, data = selection.data.split(":")

		if drop_info:
			model = treeview.get_model()
			path, position = drop_info
			iter = model.get_iter(path)
			cpu = model.get_value(iter, self.COL_CPU)
		else:
			# Move to all CPUs
			cpu = -self.nr_cpus

		if self.drop_handlers.has_key(source):
			if self.drop_handlers[source][0](cpu, data):
				self.drop_handlers[source][1].refresh()
		else:
			print "cpuview: unhandled drag source '%s'" % source

	def filter_toggled(self, cell, path, model):
		# get toggled iter
		iter = model.get_iter((int(path),))
		enabled = model.get_value(iter, self.COL_FILTER)
		cpu = model.get_value(iter, self.COL_CPU)

		enabled = not enabled

		if enabled:
			if cpu in self.cpus_filtered:
				self.cpus_filtered.remove(cpu)
		else:
			if cpu not in self.cpus_filtered:
				self.cpus_filtered.append(cpu)

		self.procview.toggle_mask_cpu(cpu, enabled)
		self.irqview.toggle_mask_cpu(cpu, enabled)

		# set new value
		model.set(iter, self.COL_FILTER, enabled)

	def refresh(self):
		self.list_store.clear()
		self.cpustats.reload()
		for cpunr in range(self.nr_cpus):
			cpu = self.list_store.append()
			usage = self.cpustats[cpunr + 1].usage
			self.list_store.set(cpu, self.COL_FILTER, cpunr not in self.cpus_filtered,
						 self.COL_CPU, cpunr,
						 self.COL_USAGE, int(usage))
		self.treeview.show_all()
		return True

def on_affinity_text_changed(self):
	new_affinity_text = self.affinity.get_text().strip()
	if self.affinity_text != new_affinity_text:
		try:
			for cpu in new_affinity_text.strip(",").split(","):
				new_affinity_cpu_entry = int(cpu, 16)
		except:
			try:
				new_affinity = tuna.cpustring_to_list(new_affinity_text)
			except:
				if len(new_affinity_text) > 0 and new_affinity_text[-1] != "-":
					# print "not a hex number"
					self.affinity.set_text(self.affinity_text)
					return
		self.affinity_text = new_affinity_text

def invalid_affinity():
	dialog = gtk.MessageDialog(None,
				   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				   gtk.MESSAGE_WARNING,
				   gtk.BUTTONS_OK,
				   "Invalid affinity, specify a list of CPUs!")
	dialog.run()
	dialog.destroy()
	return False

def thread_set_attributes(pid, threads, new_policy, new_prio, new_affinity, nr_cpus):
	changed = False
	curr_policy = schedutils.get_scheduler(pid)
	curr_prio = int(threads[pid]["stat"]["rt_priority"])
	if curr_policy != new_policy or curr_prio != new_prio:
		try:
			schedutils.set_scheduler(pid, new_policy, new_prio)
		except:
			dialog = gtk.MessageDialog(None,
						   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						   gtk.MESSAGE_WARNING,
						   gtk.BUTTONS_OK,
						   "Invalid parameters!")
			dialog.run()
			dialog.destroy()
			return False

		curr_policy = schedutils.get_scheduler(pid)
		if curr_policy != new_policy:
			print "couldn't change pid %d from %s(%d) to %s(%d)!" % \
			      ( pid, schedutils.schedstr(curr_policy),
				curr_prio,
				schedutils.schedstr(new_policy),
				new_prio)
		else:
			changed = True

	curr_affinity = schedutils.get_affinity(pid)
	try:
		new_affinity = [ int(a) for a in new_affinity.split(",") ]
	except:
		try:
			new_affinity = tuna.cpustring_to_list(new_affinity)
		except:
			new_affinity = procfs.bitmasklist(new_affinity, nr_cpus)
		
	new_affinity.sort()

	if curr_affinity != new_affinity:
		try:
			schedutils.set_affinity(pid, new_affinity)
		except:
			return invalid_affinity()

		curr_affinity = schedutils.get_affinity(pid)
		if curr_affinity != new_affinity:
			print "couldn't change pid %d from %s to %s!" % \
			      ( pid, curr_affinity, new_affinity )
		else:
			changed = True

	return changed

class irq_druid:

	def __init__(self, irqs, ps, irq):
		self.irqs = irqs
		self.ps = ps
		self.irq = irq
		self.window = gtk.glade.XML(tuna_glade, "set_irq_attributes")
		self.dialog = self.window.get_widget("set_irq_attributes")
		pixbuf = self.dialog.render_icon(gtk.STOCK_PREFERENCES,
						 gtk.ICON_SIZE_SMALL_TOOLBAR)
		self.dialog.set_icon(pixbuf)
		event_handlers = { "on_irq_affinity_text_changed" : self.on_irq_affinity_text_changed,
				   "on_sched_policy_combo_changed": self.on_sched_policy_combo_changed }
		self.window.signal_autoconnect(event_handlers)

		self.sched_pri = self.window.get_widget("irq_pri_spinbutton")
		self.sched_policy = self.window.get_widget("irq_policy_combobox")
		self.affinity = self.window.get_widget("irq_affinity_text")
		text = self.window.get_widget("irq_text")

		users = tuna.get_irq_users(irqs, irq)
		self.affinity_text = tuna.get_irq_affinity_text(irqs, irq)

		pids = ps.find_by_name("IRQ-%d" % irq)
		if pids:
			pid = pids[0]
			prio = int(ps[pid]["stat"]["rt_priority"])
			self.create_policy_model(self.sched_policy)
			self.sched_policy.set_active(schedutils.get_scheduler(pid))
			text.set_markup("IRQ <b>%u</b> (PID <b>%u</b>), pri <b>%u</b>, aff <b>%s</b>, <tt><b>%s</b></tt>" % \
					( irq, pid, prio, self.affinity_text,
					  ",".join(users)))
		else:
			self.sched_pri.set_sensitive(False)
			self.sched_policy.set_sensitive(False)
			text.set_markup("IRQ <b>%u</b>, aff <b>%s</b>, <tt><b>%s</b></tt>" % \
					( irq, self.affinity_text,
				 	  ",".join(users)))

		self.affinity.set_text(self.affinity_text)

	def create_policy_model(self, policy):
		( COL_TEXT, COL_SCHED ) = range(2)
		list_store = gtk.ListStore(gobject.TYPE_STRING,
					   gobject.TYPE_UINT)
		policy.set_model(list_store)
		renderer = gtk.CellRendererText()
		policy.pack_start(renderer, True)
		policy.add_attribute(renderer, "text", COL_TEXT)
		for pol in range(4):
			row = list_store.append()
			list_store.set(row, COL_TEXT, schedutils.schedstr(pol),
					    COL_SCHED, pol)

	def on_sched_policy_combo_changed(self, button):
		new_policy = self.sched_policy.get_active()
		if new_policy in ( SCHED_FIFO, SCHED_RR ):
			can_change_pri = True
		else:
			can_change_pri = False
		self.sched_pri.set_sensitive(can_change_pri)

	def on_irq_affinity_text_changed(self, button):
		on_affinity_text_changed(self)

	def run(self):
		changed = False
		if self.dialog.run() == gtk.RESPONSE_OK:
			new_policy = self.sched_policy.get_active()
			new_prio = self.sched_pri.get_value()
			new_affinity = self.affinity.get_text()
			pids = self.ps.find_by_name("IRQ-%d" % self.irq)
			if pids:
				if thread_set_attributes(pids[0], self.ps,
							 new_policy,
							 new_prio,
							 new_affinity,
							 self.irqs.nr_cpus):
					changed = True

			try:
				new_affinity = [ int(a) for a in new_affinity.split(",") ]
			except:
				try:
					new_affinity = tuna.cpustring_to_list(new_affinity)
				except:
					new_affinity = procfs.bitmasklist(new_affinity,
									  self.irqs.nr_cpus)

			new_affinity.sort()

			curr_affinity = self.irqs[self.irq]["affinity"]
			if curr_affinity != new_affinity:
				tuna.set_irq_affinity(self.irq,
						      procfs.hexbitmask(new_affinity,
									self.irqs.nr_cpus))
				changed = True

		self.dialog.destroy()
		return changed

class irqview:

	nr_columns = 7
	( COL_NUM, COL_PID, COL_POL, COL_PRI,
	  COL_AFF, COL_EVENTS, COL_USERS ) = range(nr_columns)
	columns = (list_store_column("IRQ"),
		   list_store_column("PID", gobject.TYPE_INT),
		   list_store_column("Policy", gobject.TYPE_STRING),
		   list_store_column("Priority", gobject.TYPE_INT),
		   list_store_column("Affinity", gobject.TYPE_STRING),
		   list_store_column("Events"),
		   list_store_column("Users", gobject.TYPE_STRING))

	def __init__(self, treeview, irqs, ps, cpus_filtered):

		self.is_root = os.getuid() == 0
		self.irqs = irqs
		self.ps = ps
		self.treeview = treeview
		self.has_threaded_irqs = tuna.has_threaded_irqs(irqs, ps)
		if not self.has_threaded_irqs:
			self.nr_columns = 4
			( self.COL_NUM,
			  self.COL_AFF,
			  self.COL_EVENTS,
			  self.COL_USERS ) = range(self.nr_columns)
			self.columns = (list_store_column("IRQ"),
					list_store_column("Affinity", gobject.TYPE_STRING),
					list_store_column("Events"),
					list_store_column("Users", gobject.TYPE_STRING))

		self.list_store = gtk.ListStore(*generate_list_store_columns_with_attr(self.columns))

		self.treeview.set_model(self.list_store)

		# Allow selecting multiple rows
		selection = treeview.get_selection()
		selection.set_mode(gtk.SELECTION_MULTIPLE)

		# Allow enable drag and drop of rows
		self.treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
						       DND_TARGETS,
						       gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
		self.treeview.connect("drag_data_get", self.on_drag_data_get_data)
		self.renderer = gtk.CellRendererText()

		for col in range(self.nr_columns):
			column = gtk.TreeViewColumn(self.columns[col].name,
						    self.renderer, text = col)
			column.set_sort_column_id(col)
			column.add_attribute(self.renderer, "weight",
					     col + self.nr_columns)
			self.treeview.append_column(column)

		self.cpus_filtered = cpus_filtered
		self.refreshing = True

	def foreach_selected_cb(self, model, path, iter, irq_list):
		irq = model.get_value(iter, self.COL_NUM)
		irq_list.append(str(irq))

	def on_drag_data_get_data(self, treeview, context,
			          selection, target_id, etime):
		treeselection = treeview.get_selection()
		irq_list = []
		treeselection.selected_foreach(self.foreach_selected_cb, irq_list)
		selection.set(selection.target, 8, "irq:" + ",".join(irq_list))

	def set_irq_columns(self, iter, irq, irq_info, nics):
		new_value = [ None ] * self.nr_columns
		users = tuna.get_irq_users(self.irqs, irq, nics)
		if self.has_threaded_irqs:
			pids = self.ps.find_by_name("IRQ-%d" % irq)
			if pids:
				pid = pids[0]
				prio = int(self.ps[pid]["stat"]["rt_priority"])
				sched = schedutils.schedstr(schedutils.get_scheduler(pid))[6:]
			else:
				sched = ""
				pid = -1
				prio = -1
			new_value[self.COL_PID] = pid
			new_value[self.COL_POL] = sched
			new_value[self.COL_PRI] = prio

		new_value[self.COL_NUM] = irq
		new_value[self.COL_AFF] = tuna.get_irq_affinity_text(self.irqs, irq)
		new_value[self.COL_EVENTS] = reduce(lambda a, b: a + b, irq_info["cpu"])
		new_value[self.COL_USERS] = ",".join(users)

		set_store_columns(self.list_store, iter, new_value)

	def show(self):
		new_irqs = []
		for sirq in self.irqs.keys():
			try:
				new_irqs.append(int(sirq))
			except:
				continue

		nics = ethtool.get_active_devices()

		row = self.list_store.get_iter_first()
		while row:
			irq = self.list_store.get_value(row, self.COL_NUM)
			# IRQ was unregistered? I.e. driver unloaded?
			if not self.irqs.has_key(irq):
				if self.list_store.remove(row):
					# removed and row now its the next one
					continue
				# Was the last one
				break
			elif tuna.irq_filtered(irq, self.irqs,
					       self.cpus_filtered,
					       self.is_root):
				new_irqs.remove(irq)
				if self.list_store.remove(row):
					# removed and row now its the next one
					continue
				# Was the last one
				break
			else:
				new_irqs.remove(irq)
				irq_info = self.irqs[irq]
				self.set_irq_columns(row, irq, irq_info, nics)

			row = self.list_store.iter_next(row)

		new_irqs.sort()
		for irq in new_irqs:
			if tuna.irq_filtered(irq, self.irqs, self.cpus_filtered,
					     self.is_root):
				continue
			row = self.list_store.append()
			irq_info = self.irqs[irq]
			self.set_irq_columns(row, irq, irq_info, nics)

		self.treeview.show_all()
	
	def refresh(self):
		if not self.refreshing:
			return
		self.irqs.reload()
		self.show()

	def refresh_toggle(self, unused):
		self.refreshing = not self.refreshing

	def edit_attributes(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.list_store.get_iter(path)
		irq = self.list_store.get_value(row, self.COL_NUM)
		if not self.irqs.has_key(irq):
			return

		dialog = irq_druid(self.irqs, self.ps, irq)
		if dialog.run():
			self.refresh(self.ps)

	def on_irqlist_button_press_event(self, treeview, event):
		if event.type != gtk.gdk.BUTTON_PRESS or event.button != 3:
			return

		self.last_x = int(event.x)
		self.last_y = int(event.y)

		menu = gtk.Menu()

		setattr = gtk.MenuItem("_Set IRQ attributes")
		if self.refreshing:
			refresh_prefix = "Sto_p refreshing the"
		else:
			refresh_prefix = "_Refresh"
		refresh = gtk.MenuItem(refresh_prefix + " IRQ list")

		menu.add(setattr)
		menu.add(refresh)

		setattr.connect_object('activate', self.edit_attributes, event)
		refresh.connect_object('activate', self.refresh_toggle, event)

		setattr.show()
		refresh.show()

		menu.popup(None, None, None, event.button, event.time)

	def toggle_mask_cpu(self, cpu, enabled):
		if not enabled:
			if cpu not in self.cpus_filtered:
				self.cpus_filtered.append(cpu)
				self.show()
		else:
			if cpu in self.cpus_filtered:
				self.cpus_filtered.remove(cpu)
				self.show()

class process_druid:

	( PROCESS_COL_PID, PROCESS_COL_NAME ) = range(2)

	def __init__(self, ps, pid, nr_cpus):
		self.ps = ps
		self.pid = pid
		self.nr_cpus = nr_cpus
		pid_info = self.ps[pid]
		self.window = gtk.glade.XML(tuna_glade, "set_process_attributes")
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
		if not ps[pid].has_key("threads"):
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
		processes.set_model(self.process_list_store)
		renderer = gtk.CellRendererText()

		for col in range(len(labels)):
			column = gtk.TreeViewColumn(labels[col], renderer, text = col)
			column.set_sort_column_id(col)
			processes.append_column(column)

	def create_policy_model(self, policy):
		( COL_TEXT, COL_SCHED ) = range(2)
		list_store = gtk.ListStore(gobject.TYPE_STRING,
					   gobject.TYPE_UINT)
		policy.set_model(list_store)
		renderer = gtk.CellRendererText()
		policy.pack_start(renderer, True)
		policy.add_attribute(renderer, "text", COL_TEXT)
		for pol in range(4):
			row = list_store.append()
			list_store.set(row, COL_TEXT, schedutils.schedstr(pol),
					    COL_SCHED, pol)

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
		cmdline = procfs.process_cmdline(self.ps[self.pid])
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
		if new_policy in ( SCHED_FIFO, SCHED_RR ):
			can_change_pri = True
		else:
			can_change_pri = False
		self.sched_pri.set_sensitive(can_change_pri)

	def on_affinity_text_changed(self, button):
		on_affinity_text_changed(self)

	def set_attributes_for_regex(self, regex, new_policy, new_prio, new_affinity):
		changed = False
		cmdline_regex = re.compile(regex)
		for match_pid in self.ps.find_by_cmdline_regex(cmdline_regex):
			if thread_set_attributes(match_pid, self.ps, new_policy,
						 new_prio, new_affinity,
						 self.nr_cpus):
				changed = True

		return changed

	def set_attributes_for_threads(self, pid, new_policy, new_prio, new_affinity):
		changed = False
		threads = self.ps[pid]["threads"]
		for tid in threads.keys():
			if thread_set_attributes(tid, threads, new_policy, new_prio,
						 new_affinity, self.nr_cpus):
				changed = True

		return changed

	def run(self):
		changed = False
		if self.dialog.run() == gtk.RESPONSE_OK:
			new_policy = int(self.sched_policy.get_active())
			new_prio = int(self.sched_pri.get_value())
			new_affinity = self.affinity.get_text()
			if self.just_this_thread.get_active():
				changed = thread_set_attributes(self.pid,
								self.ps,
								new_policy,
								new_prio,
								new_affinity,
								self.nr_cpus)
			elif self.all_these_threads.get_active():
				if thread_set_attributes(self.pid, self.ps,
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

	nr_columns = 7
	( COL_PID, COL_POL, COL_PRI, COL_AFF, COL_VOLCTXT, COL_NONVOLCTXT, COL_CMDLINE ) = range(nr_columns)
	columns = (list_store_column("PID"),
		   list_store_column("Policy", gobject.TYPE_STRING),
		   list_store_column("Priority"),
		   list_store_column("Affinity", gobject.TYPE_STRING),
		   list_store_column("VolCtxtSwitch", gobject.TYPE_INT),
		   list_store_column("NonVolCtxtSwitch", gobject.TYPE_INT),
		   list_store_column("Command Line", gobject.TYPE_STRING))

	def __init__(self, treeview, ps,
		     show_kthreads = True, show_uthreads = True,
		     cpus_filtered = None):
		self.ps = ps
		self.treeview = treeview
		self.nr_cpus = procfs.cpuinfo().nr_cpus

		if not ps[1]["status"].has_key("voluntary_ctxt_switches"):
			self.nr_columns = 5
			( self.COL_PID, self.COL_POL, self.COL_PRI,
			  self.COL_AFF, self.COL_CMDLINE ) = range(self.nr_columns)
			self.columns = (list_store_column("PID"),
					list_store_column("Policy", gobject.TYPE_STRING),
					list_store_column("Priority"),
					list_store_column("Affinity", gobject.TYPE_STRING),
					list_store_column("Command Line", gobject.TYPE_STRING))

		self.tree_store = gtk.TreeStore(*generate_list_store_columns_with_attr(self.columns))
		self.treeview.set_model(self.tree_store)

		# Allow selecting multiple rows
		selection = treeview.get_selection()
		selection.set_mode(gtk.SELECTION_MULTIPLE)

		# Allow enable drag and drop of rows
		self.treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
						       DND_TARGETS,
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
			try:
				self.treeview.set_tooltip_column(col)
			except:
				# old versions of pygtk2+ doesn't have this signal
				pass
			self.treeview.append_column(column)

		self.show_kthreads = show_kthreads
		self.show_uthreads = show_uthreads
		self.cpus_filtered = cpus_filtered
		self.refreshing = True

	def on_query_tooltip(self, treeview, x, y, keyboard_mode, tooltip):
		# FIXME: Why is that it is off by a row?
		ret = treeview.get_path_at_pos(x, y - 30)
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
		try:
			index = cmdline.index("/")
			key = cmdline[:index + 1]
			suffix_help = "\n<i>One per CPU</i>"
		except:
			key = cmdline
			suffix_help = ""
		help = tuna.kthread_help(key)
		tooltip.set_markup("<b>Kernel Thread %d (%s):</b>\n%s%s" % (pid, cmdline, help, suffix_help))
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

		try:
			new_value[self.COL_POL] = schedutils.schedstr(schedutils.get_scheduler(tid))[6:]
		except SystemError:
			return True

		new_value[self.COL_PID] = tid
		thread_affinity_list = schedutils.get_affinity(tid)
		new_value[self.COL_AFF] = tuna.list_to_cpustring(thread_affinity_list)
		try:
			new_value[self.COL_VOLCTXT] = int(thread_info["status"]["voluntary_ctxt_switches"])
			new_value[self.COL_NONVOLCTXT] = int(thread_info["status"]["nonvoluntary_ctxt_switches"])
		except:
			pass

		new_value[self.COL_CMDLINE] = procfs.process_cmdline(thread_info)

		set_store_columns(self.tree_store, iter, new_value)

		return False

	def show(self, force_refresh = False):
		# Start with the first row, if there is one, on the
		# process list. If the first time update_rows will just
		# have everthing in new_tids and append_new_tids will
		# create the rows.
		if not self.refreshing and not force_refresh:
			return
		row = self.tree_store.get_iter_first()
		self.update_rows(self.ps, row, None)
		self.treeview.show_all()
	
	def update_rows(self, threads, row, parent_row):
		new_tids = threads.keys()
		while row:
			tid = self.tree_store.get_value(row, self.COL_PID)
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
					self.set_thread_columns(row, tid, threads[tid])

					if threads[tid].has_key("threads"):
						children = threads[tid]["threads"]
					else:
						children = {}
					
					child_row = self.tree_store.iter_children(row)
					self.update_rows(children, child_row, row)
			
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
			
			if self.set_thread_columns(row, tid, threads[tid]):
				# Thread doesn't exists anymore
				self.tree_store.remove(row)
				continue

			if threads[tid].has_key("threads"):
				children = threads[tid]["threads"]
				children_list = children.keys()
				children_list.sort()
				for child in children_list:
					child_row = self.tree_store.append(row)
					if self.set_thread_columns(child_row,
								   child,
								   children[child]):
						# Thread doesn't exists anymore
						self.tree_store.remove(child_row)

	def refresh(self):
		self.ps.reload()
		self.ps.reload_threads()
		self.ps.load_cmdline()

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
		if not self.ps.has_key(pid):
			return

		dialog = process_druid(self.ps, pid, self.nr_cpus)
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
					   gtk.BUTTONS_OK, help)
		dialog.set_title(title)
		ret = dialog.run()
		dialog.destroy()

	def refresh_toggle(self, a):
		self.refreshing = not self.refreshing

	def on_processlist_button_press_event(self, treeview, event):
		if event.type != gtk.gdk.BUTTON_PRESS or event.button != 3:
			return

		self.last_x = int(event.x)
		self.last_y = int(event.y)

		menu = gtk.Menu()

		setattr = gtk.MenuItem("_Set process attributes")
		if self.refreshing:
			refresh_prefix = "Sto_p refreshing the"
		else:
			refresh_prefix = "_Refresh the "
		refresh = gtk.MenuItem(refresh_prefix + " process list")
		if self.show_kthreads:
			kthreads_prefix = "_Hide"
		else:
			kthreads_prefix = "_Show"
		kthreads = gtk.MenuItem(kthreads_prefix + " kernel threads")
		if self.show_uthreads:
			uthreads_prefix = "_Hide"
		else:
			uthreads_prefix = "_Show"
		uthreads = gtk.MenuItem(uthreads_prefix + " user threads")

		help = gtk.MenuItem("_What is this?")

		menu.add(setattr)
		menu.add(refresh)
		menu.add(kthreads)
		menu.add(uthreads)
		menu.add(help)

		setattr.connect_object('activate', self.edit_attributes, event)
		refresh.connect_object('activate', self.refresh_toggle, event)
		kthreads.connect_object('activate', self.kthreads_view_toggled, event)
		uthreads.connect_object('activate', self.uthreads_view_toggled, event)
		help.connect_object('activate', self.help_dialog, event)

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

class gui:

	def __init__(self, show_kthreads = True, show_uthreads = True, cpus_filtered = []):
		global tuna_glade

		if self.check_root():
			sys.exit(1)
		for dir in tuna_glade_dirs:
			tuna_glade = "%s/tuna_gui.glade" % dir
			if os.access(tuna_glade, os.F_OK):
				break
		self.wtree = gtk.glade.XML(tuna_glade, "mainbig_window")
		self.ps = procfs.pidstats()
		self.irqs = procfs.interrupts()
		self.window = self.wtree.get_widget("mainbig_window")

		self.procview = procview(self.wtree.get_widget("processlist"),
					 self.ps, show_kthreads, show_uthreads, cpus_filtered)
		self.irqview = irqview(self.wtree.get_widget("irqlist"),
				       self.irqs, self.ps, cpus_filtered)
		self.cpuview = cpuview(self.wtree.get_widget("cpuview"),
				       self.procview, self.irqview, cpus_filtered)

		event_handlers = { "on_mainbig_window_delete_event"    : self.on_mainbig_window_delete_event,
				   "on_processlist_button_press_event" : self.procview.on_processlist_button_press_event,
				   "on_irqlist_button_press_event"     : self.irqview.on_irqlist_button_press_event,
				   "on_cpuview_button_press_event"     : self.cpuview.on_cpuview_button_press_event }
		self.wtree.signal_autoconnect(event_handlers)

		self.ps.reload_threads()
		self.ps.load_cmdline()
		self.show()
		self.timer = gobject.timeout_add(2500, self.refresh)
		try:
			self.icon = gtk.status_icon_new_from_stock(gtk.STOCK_PREFERENCES)
			self.icon.connect("activate", self.on_status_icon_activate)
			self.icon.connect("popup-menu", self.on_status_icon_popup_menu)
		except AttributeError:
			# Old pygtk2
			pass
		pixbuf = self.window.render_icon(gtk.STOCK_PREFERENCES,
						 gtk.ICON_SIZE_SMALL_TOOLBAR)
		self.window.set_icon(pixbuf)

	def on_status_icon_activate(self, status_icon):
		if self.window.is_active():
			self.window.hide()
		else:
			self.window.present()

	def on_status_icon_popup_menu(self, icon, event_button, event_time):
		menu = gtk.Menu()

		quit = gtk.MenuItem("_Quit")
		menu.add(quit)
		quit.connect_object('activate', self.on_mainbig_window_delete_event, icon)
		quit.show()

		menu.popup(None, None, None, event_button, event_time)

	def on_mainbig_window_delete_event(self, obj, event = None):
		gtk.main_quit()

	def show(self):
		self.cpuview.refresh()
		self.irqview.show()
		self.procview.show()

	def refresh(self):
		self.ps.reload()
		self.ps.reload_threads()
		self.irqview.refresh()
		self.ps.load_cmdline()
		self.procview.show()
		return True

	def check_root(self):
		if os.getuid() == 0:
			return False

		dialog = gtk.MessageDialog(None,
					   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					   gtk.MESSAGE_WARNING,
					   gtk.BUTTONS_YES_NO,
					   "Root priviledge required\n\n" + \
					   "Some functions will not work without root " + \
					   "privilege.\nDo you want to continue?")
		ret = dialog.run()
		dialog.destroy()
		if ret == gtk.RESPONSE_NO:
			return True
		return False

	def run(self):
		gtk.main()
