# -*- python -*-
# -*- coding: utf-8 -*-

import pygtk
pygtk.require("2.0")

import gtk, gobject, os, procfs, sys
import gtk.glade
from gui.cpuview import cpuview
from gui.irqview import irqview
from gui.procview import procview

tuna_glade_dirs = [ ".", "tuna", "/usr/share/tuna" ]
tuna_glade = None

class main_gui:

	def __init__(self, show_kthreads = True, show_uthreads = True, cpus_filtered = []):
		global tuna_glade

		(app, localedir) = ('tuna', '/usr/share/locale')
		gtk.glade.bindtextdomain(app, localedir)
		gtk.glade.textdomain(app)

		if self.check_root():
			sys.exit(1)
		for dir in tuna_glade_dirs:
			tuna_glade = "%s/tuna_gui.glade" % dir
			if os.access(tuna_glade, os.F_OK):
				break
		self.wtree = gtk.glade.XML(tuna_glade, "mainbig_window", "tuna")
		self.ps = procfs.pidstats()
		self.irqs = procfs.interrupts()
		self.window = self.wtree.get_widget("mainbig_window")

		self.procview = procview(self.wtree.get_widget("processlist"),
					 self.ps, show_kthreads, show_uthreads,
					 cpus_filtered, tuna_glade)
		self.irqview = irqview(self.wtree.get_widget("irqlist"),
				       self.irqs, self.ps, cpus_filtered,
				       tuna_glade)
		self.cpuview = cpuview(self.wtree.get_widget("vpaned1"),
				       self.wtree.get_widget("hpaned2"),
				       self.wtree.get_widget("cpuview"),
				       self.procview, self.irqview, cpus_filtered)

		event_handlers = { "on_mainbig_window_delete_event"    : self.on_mainbig_window_delete_event,
				   "on_processlist_button_press_event" : self.procview.on_processlist_button_press_event,
				   "on_irqlist_button_press_event"     : self.irqview.on_irqlist_button_press_event }
		self.wtree.signal_autoconnect(event_handlers)

		self.ps.reload_threads()
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
		if not self.procview.evlist: # Poll, as we don't have perf
			self.ps.reload()
			self.ps.reload_threads()
			self.procview.show()
		self.irqview.refresh()
		return True

	def check_root(self):
		if os.getuid() == 0:
			return False

		dialog = gtk.MessageDialog(None,
					   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					   gtk.MESSAGE_WARNING,
					   gtk.BUTTONS_YES_NO,
					   "%s\n\n%s\n%s" % \
					   (_("Root privilege required"),
					    _("Some functions will not work without root privilege."),
					    _("Do you want to continue?")))
		ret = dialog.run()
		dialog.destroy()
		if ret == gtk.RESPONSE_NO:
			return True
		return False

	def run(self):
		gtk.main()
