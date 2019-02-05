# -*- python -*-
# -*- coding: utf-8 -*-

import os, procfs, sys, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk as gtk
from gi.repository import Gdk as gdk
from gi.repository import GObject as gobject

# from gtk import ListStore
from .gui.cpuview import cpuview
from .gui.irqview import irqview
from .gui.procview import procview
from .gui.commonview import commonview
from .gui.profileview import profileview
from .config import Config

tuna_glade_dirs = [ ".", "tuna", "/usr/share/tuna" ]
tuna_glade = None

class main_gui:

	def __init__(self, show_kthreads = True, show_uthreads = True, cpus_filtered = []):
		global tuna_glade

		(app, localedir) = ('tuna', '/usr/share/locale')
		# gtk.glade.bindtextdomain(app, localedir)
		# gtk.glade.textdomain(app)

		if self.check_root():
			sys.exit(1)
		for dir in tuna_glade_dirs:
			tuna_glade = "%s/tuna_gui.ui" % dir
			if os.access(tuna_glade, os.F_OK):
				break
		self.wtree = gtk.Builder()
		self.wtree.add_from_file(tuna_glade)
		self.ps = procfs.pidstats()
		self.irqs = procfs.interrupts()
		self.window = self.wtree.get_object("mainbig_window")

		self.procview = procview(self.wtree.get_object("processlist"),
					 self.ps, show_kthreads, show_uthreads,
					 cpus_filtered, self.wtree)
		self.irqview = irqview(self.wtree.get_object("irqlist"),
				       self.irqs, self.ps, cpus_filtered,
				       self.wtree)
		self.cpuview = cpuview(self.wtree.get_object("vpaned1"),
				       self.wtree.get_object("hpaned2"),
				       self.wtree.get_object("cpuview"),
				       self.procview, self.irqview, cpus_filtered)

		self.config = Config()
		self.check_env()
		self.commonview = commonview()
		self.commonview.contentTable = self.wtree.get_object("commonTbl")
		self.commonview.configFileCombo = self.wtree.get_object("profileSelector")

		self.profileview = profileview()
		self.profileview.config = self.config
		self.commonview.config = self.config
		self.profileview.commonview = self.commonview
		self.commonview.profileview = self.profileview

		self.profileview.setWtree(self.wtree)
		self.profileview.init_default_file()

		event_handlers = { "on_mainbig_window_delete_event"		: self.on_mainbig_window_destroy_event,
					"on_processlist_button_press_event"			: self.procview.on_processlist_button_press_event,
					"on_irqlist_button_press_event"				: self.irqview.on_irqlist_button_press_event,
					"on_loadProfileButton_clicked"				: self.profileview.on_loadProfileButton_clicked,
					"on_SaveButton_clicked"						: self.profileview.on_SaveButton_clicked,
					"on_UpdateButton_clicked"					: self.profileview.on_UpdateButton_clicked,
					"on_applyChanges_clicked"					: self.commonview.on_applyChanges_clicked,
					"on_undoChanges_clicked"					: self.commonview.on_undoChanges_clicked,
					"on_saveSnapshot_clicked"					: self.commonview.on_saveSnapshot_clicked,
					"on_saveTunedChanges_clicked"				: self.commonview.on_saveTunedChanges_clicked,
					"on_profileSelector_changed"				: self.commonview.on_profileSelector_changed,
					"on_profileTree_button_press_event"			: self.profileview.on_profileTree_button_press_event
		}
	
		self.wtree.connect_signals(event_handlers)

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
						 gtk.IconSize.SMALL_TOOLBAR)
		self.window.set_icon(pixbuf)

	def on_status_icon_activate(self, status_icon):
		if self.window.is_active():
			self.window.hide()
		else:
			self.window.present()

	def on_status_icon_popup_menu(self, icon, event_button, event_time):
		menu = gtk.Menu()

		quit = gtk.MenuItem("_Quit", use_underline=True)
		menu.add(quit)
		quit.connect_object('activate', self.on_mainbig_window_delete_event, icon)
		quit.show()

		menu.popup(None, None, None, event_button, event_time)

	def on_mainbig_window_destroy_event(self, obj, event = None):
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
		self.binpath = sys.executable.strip(os.path.basename(sys.executable))
		os.execv(self.binpath + 'pkexec', [sys.executable] + [self.binpath + 'tuna'] + sys.argv[1:])
		return True
	
	def check_env(self):
		if not os.path.exists(self.config.config["root"]):
			try:
				os.stat(self.config.config["root"])
			except (IOError,OSError):
				os.mkdir(self.config.config["root"])
		if not os.path.exists("/root/.local/share/"):
			try:
				os.stat("/root/.local/share/")
			except (IOError,OSError):
				os.mkdir("/root/.local/")
				os.mkdir("/root/.local/share/")
	
	def run(self):
		gtk.main()
