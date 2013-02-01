# -*- python -*-
# -*- coding: utf-8 -*-

import pygtk
pygtk.require("2.0")

from tuna import tuna, gui
import ethtool, gobject, gtk, os, procfs, schedutils

class irq_druid:

	def __init__(self, irqs, ps, irq, gladefile):
		self.irqs = irqs
		self.ps = ps
		self.irq = irq
		self.window = gtk.glade.XML(gladefile, "set_irq_attributes", "tuna")
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

		irq_re = tuna.threaded_irq_re(irq)
		pids = self.ps.find_by_regex(irq_re)
		if pids:
			pid = pids[0]
			prio = int(ps[pid]["stat"]["rt_priority"])
			self.create_policy_model(self.sched_policy)
			self.sched_policy.set_active(schedutils.get_scheduler(pid))
			self.sched_pri.set_value(prio)
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
		renderer = gtk.CellRendererText()
		policy.pack_start(renderer, True)
		policy.add_attribute(renderer, "text", COL_TEXT)
		for pol in range(4):
			row = list_store.append()
			list_store.set(row, COL_TEXT, schedutils.schedstr(pol),
					    COL_SCHED, pol)
		policy.set_model(list_store)

	def on_sched_policy_combo_changed(self, button):
		new_policy = self.sched_policy.get_active()
		if new_policy in ( schedutils.SCHED_FIFO, schedutils.SCHED_RR ):
			can_change_pri = True
		else:
			can_change_pri = False
		self.sched_pri.set_sensitive(can_change_pri)

	def on_irq_affinity_text_changed(self, button):
		gui.on_affinity_text_changed(self)

	def run(self):
		changed = False
		if self.dialog.run() == gtk.RESPONSE_OK:
			new_policy = self.sched_policy.get_active()
			new_prio = int(self.sched_pri.get_value())
			new_affinity = self.affinity.get_text()
			irq_re = tuna.threaded_irq_re(self.irq)
			pids = self.ps.find_by_regex(irq_re)
			if pids:
				if gui.thread_set_attributes(self.ps[pids[0]],
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
	columns = (gui.list_store_column(_("IRQ")),
		   gui.list_store_column(_("PID"), gobject.TYPE_INT),
		   gui.list_store_column(_("Policy"), gobject.TYPE_STRING),
		   gui.list_store_column(_("Priority"), gobject.TYPE_INT),
		   gui.list_store_column(_("Affinity"), gobject.TYPE_STRING),
		   gui.list_store_column(_("Events")),
		   gui.list_store_column(_("Users"), gobject.TYPE_STRING))

	def __init__(self, treeview, irqs, ps, cpus_filtered, gladefile):

		self.is_root = os.getuid() == 0
		self.irqs = irqs
		self.ps = ps
		self.treeview = treeview
		self.gladefile = gladefile
		self.has_threaded_irqs = tuna.has_threaded_irqs(ps)
		if not self.has_threaded_irqs:
			self.nr_columns = 4
			( self.COL_NUM,
			  self.COL_AFF,
			  self.COL_EVENTS,
			  self.COL_USERS ) = range(self.nr_columns)
			self.columns = (gui.list_store_column(_("IRQ")),
					gui.list_store_column(_("Affinity"), gobject.TYPE_STRING),
					gui.list_store_column(_("Events")),
					gui.list_store_column(_("Users"), gobject.TYPE_STRING))

		self.list_store = gtk.ListStore(*gui.generate_list_store_columns_with_attr(self.columns))

		# Allow selecting multiple rows
		selection = treeview.get_selection()
		selection.set_mode(gtk.SELECTION_MULTIPLE)

		# Allow enable drag and drop of rows
		self.treeview.enable_model_drag_source(gtk.gdk.BUTTON1_MASK,
						       gui.DND_TARGETS,
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

		self.treeview.set_model(self.list_store)

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
			irq_re = tuna.threaded_irq_re(irq)
			pids = self.ps.find_by_regex(irq_re)
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

		gui.set_store_columns(self.list_store, iter, new_value)

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
				try:
					new_irqs.remove(irq)
					irq_info = self.irqs[irq]
					self.set_irq_columns(row, irq, irq_info, nics)
				except:
					if self.list_store.remove(row):
						# removed and row now its the next one
						continue
					# Was the last one
					break

			row = self.list_store.iter_next(row)

		new_irqs.sort()
		for irq in new_irqs:
			if tuna.irq_filtered(irq, self.irqs, self.cpus_filtered,
					     self.is_root):
				continue
			row = self.list_store.append()
			irq_info = self.irqs[irq]
			try:
				self.set_irq_columns(row, irq, irq_info, nics)
			except:
				self.list_store.remove(row)

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

		dialog = irq_druid(self.irqs, self.ps, irq, self.gladefile)
		if dialog.run():
			self.refresh()

	def on_irqlist_button_press_event(self, treeview, event):
		if event.type != gtk.gdk.BUTTON_PRESS or event.button != 3:
			return

		self.last_x = int(event.x)
		self.last_y = int(event.y)

		menu = gtk.Menu()

		setattr = gtk.MenuItem(_("_Set IRQ attributes"))
		if self.refreshing:
			refresh = gtk.MenuItem(_("Sto_p refreshing the IRQ list"))
		else:
			refresh = gtk.MenuItem(_("_Refresh the IRQ list"))

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
