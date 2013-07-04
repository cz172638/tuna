import pygtk
import gtk

from tuna import tuna, gui

import os, shutil

class profileview:
	def on_loadProfileButton_clicked(self, button):
		self.dialog = gtk.FileChooserDialog("Open...", None,
			gtk.FILE_CHOOSER_ACTION_OPEN, (gtk.STOCK_CANCEL,
			gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		self.dialog.set_default_response(gtk.RESPONSE_OK)
		filter = gtk.FileFilter()
		filter.set_name("All files")
		filter.add_pattern("*")
		self.dialog.add_filter(filter)
		self.dialog.set_current_folder(self.config.config["root"])
		self.response = self.dialog.run()
		if self.response == gtk.RESPONSE_OK:
			self.addFile(self.dialog.get_filename())
			self.setProfileFileList()
		self.dialog.destroy()

	def setWtree(self, wtree):
		self.configFileTree = wtree.get_widget("profileTree")
		self.profileContent = wtree.get_widget("profileContent")
		self.configFileCombo = wtree.get_widget("profileSelector")
		self.profileDescription = wtree.get_widget("profileDescriptionText")
		self.frame = wtree.get_widget("TunableFramesw")

	def setProfileFileList(self):
		self.clearConfig()
		for val in self.config.populate():
			self.addConfig(val)
		return True

	def addFile(self,value):
		try:
			if os.path.isfile(value):
				tmp = value.rfind("/")
				shutil.copy(value, self.config.config['root']+value[tmp:len(value)])
				self.setProfileFileList()
				self.config.load(value[tmp:len(value)])
		except Exception as e:
			self.show_mbox_warning(str(e))

	def updateProfileContent(self):
		try:
			self.config.cache
		except:
			self.config.cache = ""
		self.profileContentBuffer = self.profileContent.get_buffer()
		self.profileContentBuffer.set_text(self.config.cache)

	def clearConfig(self):
		try:
			self.config_store.clear()
			self.combo_store.clear()
		except:
			pass

	def addConfig(self,config):
		if not self.configFileTree or not self.configFileCombo:
			return False
		try:
			self.configs
			self.configFileCombo
		except AttributeError:
			self.config_store = gtk.ListStore(str)
			self.configs = self.configFileTree
			self.configFileTree.append_column(gtk.TreeViewColumn('Profile Name', gtk.CellRendererText(), text=0))
			self.configHandler = self.configs.connect('cursor_changed', self.changeProfile)
			self.configs.set_model(self.config_store)
			self.combo_store = gtk.ListStore(str)
			self.configFileCombo.set_model(self.combo_store)
			cell = gtk.CellRendererText()
			self.configFileCombo.pack_start(cell, True)
			self.configFileCombo.add_attribute(cell, "text", 0)
		self.config_store.append([config])
		self.configs.show()
		self.combo_store.append([config])
		self.configFileCombo.show()

	def changeProfile(self,config):
		try:
			f = open(self.config.config['root']+self.config.cacheFileName, 'r')
			temp = f.read()
			f.close()
			self.profileContentBuffer = self.profileContent.get_buffer()
			buff = self.profileContentBuffer.get_text(self.profileContentBuffer.get_start_iter(),self.profileContentBuffer.get_end_iter())
			if temp != buff:
				dialog = gtk.MessageDialog(None,
					gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_WARNING,
						gtk.BUTTONS_YES_NO,
						"%s\n\n%s\n%s" % \
						(_("Config file was changed!"),
						_("All changes will be lost"),
						_("Realy continue?"),))
				ret = dialog.run()
				dialog.destroy()
				if ret == gtk.RESPONSE_NO:
					old = self.config.cacheFileName.rfind("/")
					old = self.config.cacheFileName[old+1:len(self.config.cacheFileName)]
					self.set_current_tree_selection(old)
					return False
		except IOError as e:
			pass
		currentFile = self.get_current_tree_selection()
		self.config.fileToCache(currentFile)
		self.updateProfileContent()
		self.profileDescription.set_text(self.config.description)

	def on_SaveButton_clicked(self, widget):
		try:
			self.profileContentBuffer = self.profileContent.get_buffer()
			self.config.cache = self.profileContentBuffer.get_text(self.profileContentBuffer.get_start_iter(),self.profileContentBuffer.get_end_iter())
			self.config.cacheToFile(self.config.cacheFileName)
		except IOError as e:
			self.show_mbox_warning(_("Cannot write to config file: %s") % (self.config.cacheFileName))

	def on_UpdateButton_clicked(self, widget):
		self.profileContentBuffer = self.profileContent.get_buffer()
		self.temp = self.profileContentBuffer.get_text(self.profileContentBuffer.get_start_iter(),self.profileContentBuffer.get_end_iter())
		try:
			if not self.config.loadDirect(self.temp):
				self.commonview.updateCommonView()
				self.config.updateDefault(self.config.cacheFileName)
				self.frame.show()
			else:
				self.frame.hide()
		except RuntimeError as e:
			self.show_mbox_warning(str(e))
			self.frame.hide()

	def init_default_file(self):
		self.setProfileFileList()
		try:
			if 'lastfile' in self.config.config and \
				not self.config.load(self.config.config['lastfile']):
				cur = self.configFileTree.get_model()
				for val in cur:
					if val[0] == self.config.config['lastfile']:
						self.configFileTree.set_cursor(val.path[0])
				self.commonview.updateCommonView()
				self.frame.show()
			else:
				self.frame.hide()
		except RuntimeError as e:
			dialog = gtk.MessageDialog(None,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
				_("%s\nRun autocorect?") % _(str(e)))
			dlgret = dialog.run()
			dialog.destroy()
			if dlgret == gtk.RESPONSE_YES:
				if 'lastfile' in self.config.config:
					self.config.fixConfigFile(self.config.config['root'] + self.config.config['lastfile'])
					err = self.config.checkConfigFile(self.config.config['root'] + self.config.config['lastfile'])
					if err != '':
						self.show_mbox_warning(_("Default %s" % str(err)))
						self.frame.hide()
					else:
						self.init_default_file()
				else:
					self.frame.hide()
			else:
				self.frame.hide()

	def on_profileTree_button_press_event(self, treeview, event):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			time = event.time
			pthinfo = treeview.get_path_at_pos(x, y)
			if pthinfo is not None:
				path, col, cellx, celly = pthinfo
				treeview.grab_focus()
				treeview.set_cursor( path, col, 0)
				context = gtk.Menu()

				item = gtk.ImageMenuItem(_("New profile"))
				item.connect("activate", self.on_menu_new)
				img = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
				img.show()
				item.set_image(img)
				context.append(item)

				item = gtk.ImageMenuItem(_("Rename"))
				item.connect("activate", self.on_menu_rename)
				img = gtk.image_new_from_stock(gtk.STOCK_FILE, gtk.ICON_SIZE_MENU)
				img.show()
				item.set_image(img)
				context.append(item)

				item = gtk.ImageMenuItem(_("Copy"))
				item.connect("activate", self.on_menu_copy)
				img = gtk.image_new_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
				img.show()
				item.set_image(img)
				context.append(item)

				item = gtk.ImageMenuItem(_("Delete"))
				item.connect("activate", self.on_menu_delete)
				img = gtk.image_new_from_stock(gtk.STOCK_DELETE, gtk.ICON_SIZE_MENU)
				img.show()
				item.set_image(img)
				context.append(item)

				item = gtk.ImageMenuItem(_("Check"))
				item.connect("activate", self.on_menu_check)
				img = gtk.image_new_from_stock(gtk.STOCK_SPELL_CHECK, gtk.ICON_SIZE_MENU)
				img.show()
				item.set_image(img)
				context.append(item)

				context.show_all()
				context.popup(None, None, None, event.button, time)
			return True

	def get_current_tree_selection(self):
		selection = self.configFileTree.get_selection()
		tree_model, tree_iter = selection.get_selected()
		return tree_model.get_value(tree_iter, 0)

	def set_current_tree_selection(self, string):
		cur = self.configFileTree.get_model()
		for val in cur:
			if val[0] == string:
				self.configFileTree.set_cursor(val.path[0])
				return True
		return False

	def on_menu_new(self, widget):
		filename = self.get_text_dialog(_("Please enter new filename"),"empty.conf")
		if(filename == None or filename == "" or os.path.exists(self.config.config['root']+filename)):
			self.show_mbox_warning(_("Bad or empty filename %s" % _(filename)))
			return False
		else:
			try:
				f = open(self.config.config['root'] + filename, 'w')
				f.write("#List of enabled categories\n")
				f.write("[categories]\n")
				f.write("#format:\n")
				f.write("#	category_identifier=Category Name\n")
				f.write("\n")
				f.write("#[category_identifier]\n")
				f.write("#value.name=default\n")
				f.write("#value.name=slider_min,slider_max,default\n")
				f.write("\n")
				f.write("#[guiAlias]\n")
				f.write("#value.name=Alias\n")
				f.write("\n")
				f.write("#[fileDescription]\n")
				f.write("#text=Description of this profile\n")
				f.write("\n")
				f.close()
				if self.setProfileFileList():
					self.set_current_tree_selection(filename)
					self.frame.hide()
			except IOError as io:
				self.show_mbox_warning(str(io))
		return True

	def on_menu_check(self, widget):
		filename = self.get_current_tree_selection()
		err = self.config.checkConfigFile(self.config.config['root']+filename)
		if err != '':
			self.show_mbox_warning("%s\n%s" % (_("Config file contain errors:"), _(err)))
			return False
		else:
			dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_INFO,\
			 gtk.BUTTONS_OK, "%s\n" % (_("Config file looks OK")))
			ret = dialog.run()
			dialog.destroy()
		self.set_current_tree_selection(filename)
		return True

	def on_menu_rename(self, widget):
		old_filename = self.get_current_tree_selection()
		new_filename = self.get_text_dialog(_("Please enter new name for %s" % (old_filename)), old_filename)
		if(new_filename == None or new_filename == ""):
			self.show_mbox_warning(_("Bad or empty filename %s" % _(new_filename)))
			return False
		else:
			try:
				os.rename(self.config.config['root'] + old_filename, self.config.config['root'] + new_filename)
				if self.setProfileFileList():
					self.set_current_tree_selection(new_filename)
				if self.config.checkConfigFile(self.config.config['root'] + new_filename) == '':
					self.commonview.updateCommonView()
				else:
					self.frame.hide()
			except OSError as io:
				self.show_mbox_warning(str(io))
		return True

	def on_menu_copy(self, widget):
		old_filename = self.get_current_tree_selection()
		new_filename = self.get_text_dialog(_("Please enter name for new file"), old_filename)
		if(new_filename == None or new_filename == ""):
			self.show_mbox_warning(_("Bad or empty filename %s" % _(new_filename)))
			return False
		else:
			try:
				shutil.copy2(self.config.config['root']+old_filename, self.config.config['root']+new_filename)
			except (shutil.Error, IOError) as e:
				self.show_mbox_warning(str(e))
			if self.setProfileFileList():
				self.set_current_tree_selection(new_filename)
			if self.config.checkConfigFile(self.config.config['root'] + new_filename) == '':
				self.commonview.updateCommonView()
			else:
				self.frame.hide()
		return True

	def on_menu_delete(self, widget):
		filename = self.get_current_tree_selection()
		dialog = gtk.MessageDialog(None,
			   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
			   gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
			   _("Profile %s will be deleted!\nReally?" % (filename)))
		ret = dialog.run()
		dialog.destroy()
		if ret == gtk.RESPONSE_YES:
			try:
				os.unlink(self.config.config['root'] + filename)
			except OSError as oe:
				self.show_mbox_warning(str(oe))
				return False
			if self.setProfileFileList():
				self.configFileTree.set_cursor(0)
				currentFile = self.get_current_tree_selection()
			if self.config.checkConfigFile(self.config.config['root'] + currentFile) == '':
				self.commonview.updateCommonView()
				return True
			else:
				self.frame.hide()
		return False

	def get_text_dialog(self, message, default=''):
		d = gtk.MessageDialog(None,
			gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
			gtk.MESSAGE_QUESTION,
			gtk.BUTTONS_OK_CANCEL,
			message)
		entry = gtk.Entry()
		entry.set_text(default)
		entry.show()
		d.vbox.pack_end(entry)
		entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
		d.set_default_response(gtk.RESPONSE_OK)
		r = d.run()
		text = entry.get_text().decode('utf8')
		d.destroy()
		if r == gtk.RESPONSE_OK:
			return text
		else:
			return None

	def show_mbox_warning(self, message):
		dialog = gtk.MessageDialog(None,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, _((str(message))))
		ret = dialog.run()
		dialog.destroy()
