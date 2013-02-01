import pygtk
pygtk.require("2.0")

import gobject, gtk, pango, procfs, schedutils
from tuna import tuna

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
				if len(new_affinity_text) > 0 and new_affinity_text[-1] != '-' and new_affinity_text[0:2] not in ('0x', '0X'):
					# print "not a hex number"
					self.affinity.set_text(self.affinity_text)
					return
		self.affinity_text = new_affinity_text

def invalid_affinity():
	dialog = gtk.MessageDialog(None,
				   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				   gtk.MESSAGE_WARNING,
				   gtk.BUTTONS_OK,
				   _("Invalid affinity, specify a list of CPUs!"))
	dialog.run()
	dialog.destroy()
	return False

def thread_set_attributes(pid_info, new_policy, new_prio, new_affinity, nr_cpus):
	pid = pid_info.pid
	changed = False
	curr_policy = schedutils.get_scheduler(pid)
	curr_prio = int(pid_info["stat"]["rt_priority"])
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
						   _("Invalid parameters!"))
			dialog.run()
			dialog.destroy()
			return False

		curr_policy = schedutils.get_scheduler(pid)
		if curr_policy != new_policy:
			print _("couldn't change pid %(pid)d from %(cpol)s(%(cpri)d) to %(npol)s(%(npri)d)!") % \
			      { 'pid': pid, 'cpol': schedutils.schedstr(curr_policy),
				'cpri': curr_prio,
				'npol': schedutils.schedstr(new_policy),
				'npri': new_prio}
		else:
			changed = True

	try:
		curr_affinity = schedutils.get_affinity(pid)
	except (SystemError, OSError) as e: # (3, 'No such process') old python-schedutils incorrectly raised SystemError
		if e[0] == 3:
			return False
		raise e

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
		except (SystemError, OSError) as e: # (3, 'No such process') old python-schedutils incorrectly raised SystemError
			if e[0] == 3:
				return False
			raise e

		if curr_affinity != new_affinity:
			print _("couldn't change pid %(pid)d from %(caff)s to %(naff)s!") % \
			      { 'pid':pid, 'caff':curr_affinity, 'naff':new_affinity }
		else:
			changed = True

	return changed
