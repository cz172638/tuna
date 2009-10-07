# -*- python -*-
# -*- coding: utf-8 -*-

import pygtk
pygtk.require("2.0")

import gtk, gobject, math, os, procfs, schedutils
from tuna import sysfs, tuna, gui

def set_affinity_warning(tid, affinity):
	dialog = gtk.MessageDialog(None,
				   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				   gtk.MESSAGE_WARNING,
				   gtk.BUTTONS_OK,
				   _("Couldn't change the affinity of %(tid)d to %(affinity)s!") % \
					{"tid": tid, "affinity": affinity})
	dialog.run()
	dialog.destroy()

def drop_handler_move_threads_to_cpu(new_affinity, data):
	pid_list = [ int(pid) for pid in data.split(",") ]

	return tuna.move_threads_to_cpu(new_affinity, pid_list,
					set_affinity_warning)

def drop_handler_move_irqs_to_cpu(cpus, data):
	irq_list = [ int(irq) for irq in data.split(",") ]
	new_affinity = [ reduce(lambda a, b: a | b,
			      map(lambda cpu: 1 << cpu, cpus)), ]

	for irq in irq_list:
		tuna.set_irq_affinity(irq, new_affinity)

	# FIXME: check if we really changed the affinity, but
	# its only an optimization to avoid a needless refresh
	# in the irqview, now we always refresh.
	return True

class cpu_socket_frame(gtk.Frame):

	( COL_FILTER, COL_CPU, COL_USAGE ) = range(3)

	def __init__(self, socket, cpus, creator):

		if creator.nr_sockets > 1:
			gtk.Frame.__init__(self, _("Socket %s") % socket)
		else:
			gtk.Frame.__init__(self)

		self.socket = socket
		self.cpus = cpus
		self.nr_cpus = len(cpus)
		self.creator = creator

		self.list_store = gtk.ListStore(gobject.TYPE_BOOLEAN,
						gobject.TYPE_UINT,
						gobject.TYPE_UINT)

		self.treeview = gtk.TreeView(self.list_store)

		# Filter column
		renderer = gtk.CellRendererToggle()
		renderer.connect('toggled', self.filter_toggled, self.list_store)
		column = gtk.TreeViewColumn(_('Filter'), renderer, active = self.COL_FILTER)
		self.treeview.append_column(column)

		# CPU# column
		column = gtk.TreeViewColumn(_('CPU'), gtk.CellRendererText(),
					    text = self.COL_CPU)
		self.treeview.append_column(column)

		# CPU usage column
		try:
			column = gtk.TreeViewColumn(_('Usage'), gtk.CellRendererProgress(),
						    text = self.COL_USAGE, value = self.COL_USAGE)
		except:
			# CellRendererProgress needs pygtk2 >= 2.6
			column = gtk.TreeViewColumn(_('Usage'), gtk.CellRendererText(),
						    text = self.COL_USAGE)
		self.treeview.append_column(column)

		self.add(self.treeview)

		self.treeview.enable_model_drag_dest(gui.DND_TARGETS,
						     gtk.gdk.ACTION_DEFAULT)
		self.treeview.connect("drag_data_received",
		 		       self.on_drag_data_received_data)
		self.treeview.connect("button_press_event",
		 		       self.on_cpu_socket_frame_button_press_event)

		self.drop_handlers = { "pid": (drop_handler_move_threads_to_cpu, self.creator.procview),
				       "irq": (drop_handler_move_irqs_to_cpu, self.creator.irqview), }

		self.drag_dest_set(gtk.DEST_DEFAULT_ALL, gui.DND_TARGETS,
				   gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
		self.connect("drag_data_received",
			     self.on_frame_drag_data_received_data)

	def on_frame_drag_data_received_data(self, w, context, x, y,
					     selection, info, etime):
		# Move to all CPUs in this socket
		cpus = [ int(cpu.name[3:]) for cpu in self.cpus ]
		# pid list, a irq list, etc
		source, data = selection.data.split(":")

		if self.drop_handlers.has_key(source):
			if self.drop_handlers[source][0](cpus, data):
				self.drop_handlers[source][1].refresh()
		else:
			print "cpu_socket_frame: unhandled drag source '%s'" % source

	def on_drag_data_received_data(self, treeview, context, x, y,
				       selection, info, etime):
		drop_info = treeview.get_dest_row_at_pos(x, y)

		# pid list, a irq list, etc
		source, data = selection.data.split(":")

		if drop_info:
			model = treeview.get_model()
			path, position = drop_info
			iter = model.get_iter(path)
			cpus = [ model.get_value(iter, self.COL_CPU), ]
		else:
			# Move to all CPUs in this socket
			cpus = [ int(cpu.name[3:]) for cpu in self.cpus ]

		if self.drop_handlers.has_key(source):
			if self.drop_handlers[source][0](cpus, data):
				self.drop_handlers[source][1].refresh()
		else:
			print "cpu_socket_frame: unhandled drag source '%s'" % source

	def refresh(self):
		self.list_store.clear()
		for i in range(self.nr_cpus):
			cpu = self.cpus[i]
			cpunr = int(cpu.name[3:])
			usage = self.creator.cpustats[cpunr + 1].usage

			iter = self.list_store.append()
			self.list_store.set(iter,
					    self.COL_FILTER, cpunr not in self.creator.cpus_filtered,
					    self.COL_CPU, cpunr,
					    self.COL_USAGE, int(usage))
		self.treeview.show_all()

	def isolate_cpu(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.list_store.get_iter(path)
		cpu = self.list_store.get_value(row, self.COL_CPU)

		self.creator.isolate_cpus([cpu,])

	def include_cpu(self, a):
		ret = self.treeview.get_path_at_pos(self.last_x, self.last_y)
		if not ret:
			return
		path, col, xpos, ypos = ret
		if not path:
			return
		row = self.list_store.get_iter(path)
		cpu = self.list_store.get_value(row, self.COL_CPU)

		self.creator.include_cpus([cpu,])

	def restore_cpu(self, a):

		self.creator.restore_cpu()

	def isolate_cpu_socket(self, a):

		# Isolate all CPUs in this socket
		cpus = [ int(cpu.name[3:]) for cpu in self.cpus ]
		self.creator.isolate_cpus(cpus)

	def include_cpu_socket(self, a):

		# Include all CPUs in this socket
		cpus = [ int(cpu.name[3:]) for cpu in self.cpus ]
		self.creator.include_cpus(cpus)

	def on_cpu_socket_frame_button_press_event(self, treeview, event):
		if event.type != gtk.gdk.BUTTON_PRESS or event.button != 3:
			return

		self.last_x = int(event.x)
		self.last_y = int(event.y)

		menu = gtk.Menu()

		include = gtk.MenuItem(_("I_nclude CPU"))
		isolate = gtk.MenuItem(_("_Isolate CPU"))
		if self.creator.nr_sockets > 1:
			include_socket = gtk.MenuItem(_("I_nclude CPU Socket"))
			isolate_socket = gtk.MenuItem(_("_Isolate CPU Socket"))
		restore = gtk.MenuItem(_("_Restore CPU"))

		menu.add(include)
		menu.add(isolate)
		if self.creator.nr_sockets > 1:
			menu.add(include_socket)
			menu.add(isolate_socket)
		menu.add(restore)

		include.connect_object('activate', self.include_cpu, event)
		isolate.connect_object('activate', self.isolate_cpu, event)
		if self.creator.nr_sockets > 1:
			include_socket.connect_object('activate', self.include_cpu_socket, event)
			isolate_socket.connect_object('activate', self.isolate_cpu_socket, event)
		if not (self.creator.previous_pid_affinities or \
			self.creator.previous_irq_affinities):
			restore.set_sensitive(False)
		restore.connect_object('activate', self.restore_cpu, event)

		include.show()
		isolate.show()
		if self.creator.nr_sockets > 1:
			include_socket.show()
			isolate_socket.show()
		restore.show()

		menu.popup(None, None, None, event.button, event.time)

	def filter_toggled(self, cell, path, model):
		# get toggled iter
		iter = model.get_iter((int(path),))
		enabled = model.get_value(iter, self.COL_FILTER)
		cpu = model.get_value(iter, self.COL_CPU)

		enabled = not enabled
		self.creator.toggle_mask_cpu(cpu, enabled)

		# set new value
		model.set(iter, self.COL_FILTER, enabled)

class cpuview:

	def __init__(self, vpaned, hpaned, window, procview, irqview, cpus_filtered):
		self.cpus = sysfs.cpus()
		self.cpustats = procfs.cpusstats()
		self.socket_frames = {}

		self.procview = procview
		self.irqview = irqview

		vbox = window.get_child().get_child()
		socket_ids = [ int(id) for id in self.cpus.sockets.keys() ]
		socket_ids.sort()

		self.nr_sockets = len(socket_ids)
		if self.nr_sockets > 1:
			columns = math.ceil(math.sqrt(self.nr_sockets))
			rows = math.ceil(self.nr_sockets / columns)
			box = gtk.HBox()
			vbox.pack_start(box, True, True)
		else:
			box = vbox

		column = 1
		for socket_id in socket_ids:
			frame = cpu_socket_frame(socket_id,
						 self.cpus.sockets[str(socket_id)],
						 self)
			box.pack_start(frame, False, False)
			self.socket_frames[socket_id] = frame
			if self.nr_sockets > 1:
				if column == columns:
					box = gtk.HBox()
					vbox.pack_start(box, True, True)
					column = 1
				else:
					column += 1

		window.show_all()

		self.cpus_filtered = cpus_filtered
		self.refresh()

		self.previous_pid_affinities = None
		self.previous_irq_affinities = None

		req = frame.size_request()
		# FIXME: what is the slack we have
		# to add to every row and column?
		width = req[0] + 16
		height = req[1] + 20
		if self.nr_sockets > 1:
			width *= columns
			height *= rows
		vpaned.set_position(int(height))
		hpaned.set_position(int(width))

		self.timer = gobject.timeout_add(3000, self.refresh)

	def isolate_cpus(self, cpus):
		self.previous_pid_affinities, \
		  self.previous_irq_affinities = tuna.isolate_cpus(cpus, self.cpus.nr_cpus)

		if self.previous_pid_affinities:
			self.procview.refresh()

		if self.previous_irq_affinities:
			self.irqview.refresh()

	def include_cpus(self, cpus):
		self.previous_pid_affinities, \
		  self.previous_irq_affinities = tuna.include_cpus(cpus, self.cpus.nr_cpus)

		if self.previous_pid_affinities:
			self.procview.refresh()

		if self.previous_irq_affinities:
			self.irqview.refresh()

	def restore_cpu(self):
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
								self.cpus.nr_cpus))

		self.previous_pid_affinities = None
		self.previous_irq_affinities = None

	def toggle_mask_cpu(self, cpu, enabled):
		if enabled:
			if cpu in self.cpus_filtered:
				self.cpus_filtered.remove(cpu)
		else:
			if cpu not in self.cpus_filtered:
				self.cpus_filtered.append(cpu)

		self.procview.toggle_mask_cpu(cpu, enabled)
		self.irqview.toggle_mask_cpu(cpu, enabled)

	def refresh(self):
		self.cpustats.reload()
		for frame in self.socket_frames.keys():
			self.socket_frames[frame].refresh()
		return True
