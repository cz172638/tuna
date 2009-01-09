import pygtk
pygtk.require("2.0")

import gobject, gtk, pango, procfs, schedutils, tuna

class list_store_column:
	def __init__(self, name, type = gobject.TYPE_UINT):
		self.name = name
		self.type = type

def generate_list_store_columns_with_attr(columns):
	for column in columns:
		yield column.type
	for column in columns:
		yield gobject.TYPE_UINT

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
	if new_policy == schedutils.SCHED_OTHER:
		new_prio = 0
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

	try:
		curr_affinity = schedutils.get_affinity(pid)
	except SystemError: # (3, 'No such process')
		return False

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

		try:
			curr_affinity = schedutils.get_affinity(pid)
		except SystemError: # (3, 'No such process')
			return False
		if curr_affinity != new_affinity:
			print "couldn't change pid %d from %s to %s!" % \
			      ( pid, curr_affinity, new_affinity )
		else:
			changed = True

	return changed