import pygtk
import gtk
from tuna import tuna, gui

class commonview:
	def updateCommonView(self):
		try:
			self.contentTable
			self.config
		except:
			pass
		self.cleanUp()
		self.setup()

	def cleanUp(self):
		for value in self.contentTable.get_children():
			if value.get_name() == "controls":
				self.ctrl = value
			if value.get_name() == "profileSelectorBox":
				self.selector = value
			self.contentTable.remove(value)

	def setup(self):
		try:
			self.contentTable.set_homogeneous(False)
			catListlenght = len(self.config.categories)
			if catListlenght <= 0:
				return False
			row = ((catListlenght+(catListlenght%2))/2)-catListlenght%2
			frames = {}
			frameContent = {}
			catCntr = 0
			contentCntr = 0
			self.contentTable.resize(row+3,2)
			self.contentTable.attach(self.ctrl,0,2,1,2,gtk.FILL,gtk.FILL)
			self.contentTable.attach(self.selector,0,2,0,1,gtk.FILL,gtk.FILL)
			cur = self.profileview.configFileCombo.get_model()
			for val in cur:
				if val[0] == self.config.cacheFileName:
					try:
						self.configFileCombo.handler_block_by_func(self.on_profileSelector_changed)
					except TypeError as e:
						pass
					self.configFileCombo.set_active(val.path[0])
					try:
						self.configFileCombo.handler_unblock_by_func(self.on_profileSelector_changed)
					except TypeError as e:
						pass
			while catCntr < catListlenght:
				frames[catCntr] = gtk.Frame()
				tLabel = gtk.Label('<b>'+self.config.categories[catCntr]+'</b>')
				tLabel.set_use_markup(True)
				frames[catCntr].set_label_widget(tLabel)
				frameContent[catCntr] = {}
				frameContent[catCntr]['labels'] = {}
				frameContent[catCntr]['texts'] = {}
				frameContent[catCntr]['tooltips'] = {}
				currentCol = catCntr%2
				currentRow = (catCntr/2)+2
				if len(self.config.ctlParams[catCntr]) > 0:
					frameContent[catCntr]['table'] = gtk.Table(len(self.config.ctlParams[catCntr]),2,False)
				else:
					frameContent[catCntr]['table'] = gtk.Table(1,2,False)
				contentCntr = 0
				for val in sorted(self.config.ctlParams[catCntr], key=str.lower):
					if self.config.getSystemValue(val) != self.config.ctlParams[catCntr][val]:
						star = "*"
					else:
						star = ""
					frameContent[catCntr]['labels'][contentCntr] = gtk.Label(self.config.originalToAlias(val)+star)
					frameContent[catCntr]['labels'][contentCntr].set_alignment(0,0.5)
					frameContent[catCntr]['tooltips'][contentCntr] = tuna.proc_sys_help(val)
					if len(frameContent[catCntr]['tooltips'][contentCntr]):
						frameContent[catCntr]['labels'][contentCntr].set_tooltip_text(frameContent[catCntr]['tooltips'][contentCntr])
					if val in self.config.ctlGuiParams[catCntr]:
						# scale control
						frameContent[catCntr]['texts'][contentCntr] = gtk.HScale()
						frameContent[catCntr]['texts'][contentCntr].set_range(self.config.ctlGuiParams[catCntr][val][0], self.config.ctlGuiParams[catCntr][val][1])
						frameContent[catCntr]['texts'][contentCntr].set_update_policy(gtk.UPDATE_CONTINUOUS)
						frameContent[catCntr]['texts'][contentCntr].set_value(int(self.config.ctlParams[catCntr][val]))
						frameContent[catCntr]['texts'][contentCntr].set_digits(0)
					else:
						# input field
						frameContent[catCntr]['texts'][contentCntr] = gtk.Entry(256)
						frameContent[catCntr]['texts'][contentCntr].set_alignment(0)
						frameContent[catCntr]['texts'][contentCntr].set_text(self.config.ctlParams[catCntr][val])
					frameContent[catCntr]['texts'][contentCntr].connect("button-release-event", self.checkStar, catCntr, contentCntr, val, frameContent[catCntr]['labels'][contentCntr])
					frameContent[catCntr]['texts'][contentCntr].connect("focus-out-event", self.checkStar, catCntr,contentCntr,val, frameContent[catCntr]['labels'][contentCntr])
					frameContent[catCntr]['table'].attach(frameContent[catCntr]['labels'][contentCntr],0,1,contentCntr,contentCntr+1,gtk.FILL,xpadding=5)
					frameContent[catCntr]['table'].attach(frameContent[catCntr]['texts'][contentCntr],1,2,contentCntr,contentCntr+1,xpadding=10)
					contentCntr = contentCntr+1
				frames[catCntr].add(frameContent[catCntr]['table'])
				self.contentTable.attach(frames[catCntr],currentCol,currentCol+1,currentRow,currentRow+1,gtk.FILL | gtk.EXPAND,gtk.FILL,1,1)
				catCntr = catCntr+1
			self.ctrl.set_padding(5,5,0,5)
			self.contentTable.set_border_width(5)
			self.contentTable.show_all()
		except AttributeError as e:
			return False

	def guiSnapshot(self):
		self.ret = {}
		self.property_cntr = 0
		for value in self.contentTable.get_children():
			if value.get_name() == "controls" or value.get_name() == "profileSelectorBox":
				continue
			self.ret[value.get_label()] = {}
			for content in value:
				if content.get_name() != "GtkTable":
					continue
				self.property_cntr = 0
				for content_last in content.get_children():
					if not content.child_get_property(content_last,"top-attach") in self.ret[value.get_label()]:
						self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")] = {}
					if content_last.get_name() == "GtkLabel":
						self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")]['label'] = content_last.get_label()
					else:
						if content_last.get_name() == "GtkEntry":
							self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")]['value'] = content_last.get_text()
						else:
							self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")]['value'] = str(int(content_last.get_value()))
		return self.ret

	def systemSnapshot(self):
		self.ret = {}
		self.property_cntr = 0
		for value in self.contentTable.get_children():
			if value.get_name() == "controls" or value.get_name() == "profileSelectorBox":
				continue
			self.ret[value.get_label()] = {}
			for content in value:
				if content.get_name() != "GtkTable":
					continue
				self.property_cntr = 0
				for content_last in content.get_children():
					if not content.child_get_property(content_last,"top-attach") in self.ret[value.get_label()]:
						self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")] = {}
					if content_last.get_name() == "GtkLabel":
						self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")]['label'] = content_last.get_label()
						self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")]['value'] = self.config.getSystemValue(self.ret[value.get_label()][content.child_get_property(content_last,"top-attach")]['label'])
		return self.ret

	def on_applyChanges_clicked(self,widget):
		self.config.backup = self.systemSnapshot()
		self.config.applyChanges(self.guiSnapshot())
		self.updateCommonView()

	def on_undoChanges_clicked(self,widget):
		try:
			self.config.backup
			self.config.applyChanges(self.config.backup)
			self.updateCommonView()
		except:
			dialog = gtk.MessageDialog(None,
					gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
					gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
					_("Backup not found, this button is useable after click on apply"))
			ret = dialog.run()
			dialog.destroy()

	def on_saveSnapshot_clicked(self,widget):
		ret = self.guiSnapshot()
		self.config.saveSnapshot(self.ret)
		old_name = self.get_current_combo_selection()
		if self.profileview.setProfileFileList():
			self.profileview.set_current_tree_selection(old_name[1])
			self.set_current_combo_selection(old_name[1])

	def on_saveTunedChanges_clicked(self,widget):
		if not self.config.checkTunedDaemon():
			dialog = gtk.MessageDialog(None,gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, _("Tuned daemon undetected!\nFor this function you must have installed Tuned daemon."))
			ret = dialog.run()
			dialog.destroy()
			return False
		dialog = gtk.MessageDialog(None,
			   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
			   gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
			   _("This function can create new profile for tuned daemon and apply config permanently after reboot.\nProfile will be permanently saved and rewrite all old profiles created by tuna!\nUsing this only if you know that config cant corrupt your system!\nRealy can do it?"))
		ret = dialog.run()
		dialog.destroy()
		if ret == gtk.RESPONSE_NO:
			return False
		try:
			ret = self.guiSnapshot()
			self.config.saveTuned(ret)
		except RuntimeError as e:
			dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,str(e))
			ret = dialog.run()
			dialog.destroy()
		self.profileview.setProfileFileList()

	def on_profileSelector_changed(self, widget):
		ret = self.get_current_combo_selection()
		if ret[0] < 0:
			return False
		self.restoreConfig = False
		err = self.config.checkConfigFile(self.config.config['root']+ret[1])
		if err != '':
			self.restoreConfig = True
			dialog = gtk.MessageDialog(None,
				gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
				gtk.MESSAGE_WARNING, gtk.BUTTONS_YES_NO,
				_("Config file contain errors: \n%s\nRun autocorrect?") % _(err))
			dlgret = dialog.run()
			dialog.destroy()
			if dlgret == gtk.RESPONSE_YES:
				self.config.fixConfigFile(self.config.config['root'] + ret[1])
				err = self.config.checkConfigFile(self.config.config['root'] + ret[1])
				if err != '':
					dialog = gtk.MessageDialog(None,
						gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_ERROR, gtk.BUTTONS_OK,
						_("Config file contain errors: \n%s\nAutocorrect failed!") % _(err))
					dialog.run()
					dialog.destroy()
					self.restoreConfig = True
				else:
					dialog = gtk.MessageDialog(None,
						gtk.DIALOG_DESTROY_WITH_PARENT,
						gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
						_("Autocorrect OK"))
					dialog.run()
					dialog.destroy()
					self.restoreConfig = False
		if self.restoreConfig:
			old = self.config.cacheFileName.rfind("/")
			old = self.config.cacheFileName[old+1:len(self.config.cacheFileName)]
			cur = self.configFileCombo.get_model()
			for val in cur:
				if val[0] == old:
					self.configFileCombo.handler_block_by_func(self.on_profileSelector_changed)
					self.configFileCombo.set_active(val.path[0])
					self.configFileCombo.handler_unblock_by_func(self.on_profileSelector_changed)
			return False
		cur = self.profileview.configFileTree.get_model()
		for val in cur:
			if val[0] == ret[1]:
				self.configFileCombo.handler_block_by_func(self.on_profileSelector_changed)
				self.profileview.configFileTree.set_cursor(val.path[0])
				self.configFileCombo.handler_unblock_by_func(self.on_profileSelector_changed)
		self.config.loadTuna(ret[1])
		self.config.updateDefault(ret[1])
		self.updateCommonView()
		return True

	def get_current_combo_selection(self):
		combo_iter = self.configFileCombo.get_active_iter()
		combo_row = self.configFileCombo.get_active()
		if combo_iter != None:
			model = self.configFileCombo.get_model()
			return (combo_row,model[combo_iter][0])
		else:
			return (-1,"ERROR")

	def set_current_combo_selection(self, string):
		cur = self.configFileCombo.get_model()
		for val in cur:
			if val[0] == string:
				self.configFileCombo.set_active(val.path[0])

	def checkStar(self, widget, event, catCntr,contentCntr,val,label):
		lbl = label.get_label().replace("*","");
		if widget.get_name() == "GtkEntry":
			value = widget.get_text()
		else:
			value = str(int(widget.get_value()))
		if value != self.config.getSystemValue(lbl):
			label.set_label(lbl+"*")
		else:
			label.set_label(lbl)
