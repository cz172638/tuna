import io, os, re, fnmatch
import sys, gtk, pygtk
import codecs, ConfigParser
from time import localtime, strftime

class Config:
	#init config, load /etc/tuna.conf (if not exist, create it)
	def __init__(self):
		self.aliasList = []
		self.aliasReverse = []
		self.configFile = "/etc/tuna.conf"

		try:
			self.configParser = ConfigParser.RawConfigParser()
			self.configParser.read(self.configFile)
			cfg = self.configParser.items('global')
		except ConfigParser.Error:
			f = open(self.configFile,'w')
			f.write("[global]\n")
			f.write("root=/etc/tuna/\n")
			f.write("lastFile=\n")
			f.close()
			self.configParser.read(self.configFile)
			cfg = self.configParser.items('global')
		self.config = {}

		for option, value in cfg:
			self.config[option] = value
		self.cacheFileName = ''

	def updateDefault(self, filename):
		if filename.replace("", "temp-direct-load.conf") != filename:
			self.temp = ConfigParser.RawConfigParser()
			self.temp.read(self.configFile)
			self.temp.set('global', 'lastFile', filename)
			with open(self.configFile, 'wb') as cfgfile:
				self.temp.write(cfgfile)

	def load(self, profileName):
		tmp = ConfigParser.RawConfigParser()
		tmp.read(self.config['root'] + profileName)
		try:
			check = tmp.items('categories')
		except ConfigParser.NoSectionError:
			if(self.tuned2Tuna(profileName) < 0):
				return -1
		return self.loadTuna(profileName)

	def loadTuna(self, profileName):
		err = self.checkConfigFile(self.config['root'] + profileName)
		if err != '':
			raise RuntimeError(_("Config file contain errors: ") + _(err))
			return -1
		try:
			self.configParser = ConfigParser.RawConfigParser()
			self.configParser.read(self.config['root'] + profileName)
			tempCategories = self.configParser.items('categories')
			self.catIndex = 0
			self.categoriesOrigin = {}
			self.categories = {}
			self.ctlParams = {}
			self.ctlGuiParams = {}
			self.aliasList = []
			self.aliasReverse = []
			for option, value in tempCategories:
				if value != "":
					oldTempCfg = self.configParser.items(option)
					self.ctlParams[self.catIndex] = {}
					self.ctlGuiParams[self.catIndex] = {}
					tempCfg = []
					for index in range(len(oldTempCfg)):
						if self.isFnString(oldTempCfg[index][0]):
							expanded = self.getFilesByFN("/proc/sys", oldTempCfg[index][0].replace(".", "/"))
							for index2 in range(len(expanded)):
								expandedData = (expanded[index2].replace("/", "."), oldTempCfg[index][1])
								tempCfg.append(expandedData)
						else:
							tempCfg.append(oldTempCfg[index])
					for opt, val in tempCfg:
						if val.find(',') != -1 and val.find(',',val.find(',')) != -1 and len(val.split(",")) > 2:
							self.ctlGuiParams[self.catIndex][opt] = val.split(",")
							val = self.ctlGuiParams[self.catIndex][opt][2]
						sys = self.getSystemValue(opt)
						if val == "" or val == sys:
							self.ctlParams[self.catIndex][opt] = sys
						else:
							self.ctlParams[self.catIndex][opt] = val
						if opt in self.ctlGuiParams[self.catIndex]:
							if self.ctlGuiParams[self.catIndex][opt][0] == '':
								self.ctlGuiParams[self.catIndex][opt][0] = int(int(self.ctlParams[self.catIndex][opt])/10)
							else:
								self.ctlGuiParams[self.catIndex][opt][0] = int(self.ctlGuiParams[self.catIndex][opt][0])
							if self.ctlGuiParams[self.catIndex][opt][1] == '':
								self.ctlGuiParams[self.catIndex][opt][1] = int(int(self.ctlParams[self.catIndex][opt])*10)
							else:
								self.ctlGuiParams[self.catIndex][opt][1] = int(self.ctlGuiParams[self.catIndex][opt][1])
					self.categories[self.catIndex] = value
					self.categoriesOrigin[self.catIndex] = option
					self.catIndex = self.catIndex + 1
		except (ConfigParser.Error, IOError):
			print _("Config file is corrupted")
			return -1
		try:
			self.aliasList = self.configParser.items('guiAlias')
		except ConfigParser.Error:
			self.aliasList = []
		self.aliasReverse = []
		return 0

	def updateDescription(self, filename):
		try:
			self.temp = ConfigParser.RawConfigParser()
			self.temp.read(self.config['root'] + filename)
			self.description = self.temp.items('fileDescription')
			self.description = dict(self.description)['text']
		except ConfigParser.Error as e:
			self.description = _("Description for this profile not found")
			if e != ConfigParser.NoSectionError:
				print e
		return self.description

	def fileToCache(self, profileName):
		try:
			f = open(self.config['root'] + profileName, 'r')
		except IOError:
			pass
		if f is None:
			raise RuntimeError(_("Cant open this config file: %s" % (self.config['root'] + profileName)))
			return False
		self.cacheFileName = profileName
		self.cache = f.read()
		f.close()
		self.updateDescription(profileName)

	def cacheToFile(self, profileName):
		try:
			f = open(self.config['root'] + profileName, 'w')
			f.write(self.cache)
			f.close()
		except IOError:
			print _("Cant write to config file: %s" % (self.config['root'] + profileName))

	def loadDirect(self, data):
		try:
			f = open(self.config['root']+"temp-direct-load.conf", 'w')
		except IOError:
			raise RuntimeError(_("Cant open this config file: %stemp-direct-load.conf" % (self.config['root'])))
		f.write(data)
		f.close()
		ret = self.load("temp-direct-load.conf")
		os.unlink(self.config['root']+"temp-direct-load.conf")
		return ret

	def populate(self):
		return [files for files in os.listdir(self.config['root'])]
	
	def getSystemValue(self, filename):
		filename = self.aliasToOriginal(filename)
		try:
			buffer = open("/proc/sys/" + filename.replace(".", "/"), 'r').read()
		except IOError:
			print _("Invalid item! file: /proc/sys/%s" %(filename.replace(".", "/")))
			return ""
		return buffer.strip()

	def setSystemValue(self, filename, value):
		filename = self.aliasToOriginal(filename)
		old = self.getSystemValue(filename)
		if value == "" or old == value:
			return 0
		try:
			fp = open("/proc/sys/" + filename.replace(".", "/"), 'w')
			fp.write(value)
		except IOError:
			print "%s%s %s %s" % (_("Cant write to file! path: /proc/sys/"), filename.replace(".","/"), _("value:"), value)
			return -1
		return 0

	def applyChanges(self, data):
		for cat in data:
			for itemId in data[cat]:
				self.setSystemValue(data[cat][itemId]['label'], data[cat][itemId]['value'])
		self.reloadSystemValues(data)

	def reloadSystemValues(self, data):
		for cat in self.ctlParams:
			for param in self.ctlParams[cat]:
				sys = self.getSystemValue(param)
				self.ctlParams[cat][param] = sys

	def aliasToOriginal(self, string):
		string = string.replace("*","")
		if string in dict(self.aliasReverse):
			return dict(self.aliasReverse)[string]
		return string

	def originalToAlias(self, string):
		tmpString = string
		for src,dst in self.aliasList:
			tmpString = tmpString.replace(src,dst)
			if string != tmpString:
				self.aliasReverse[len(self.aliasReverse):] = [(tmpString,string)]
				return tmpString
		return string

	def saveSnapshot(self,data):
		tempconfig = ConfigParser.RawConfigParser()
		tempconfig.readfp(io.BytesIO(self.cache))
		snapcat = tempconfig.items('categories')
		out = {}
		cats = {}
		for opt,val in snapcat:
			for index in range(len(data[val])):
				data[val][index]['label'] = self.aliasToOriginal(data[val][index]['label'])
				out[data[val][index]['label']] = data[val][index]['value']
		for opt,val in snapcat:
			snapcontPacked = tempconfig.items(opt)
			snapcont = []
			for index in range(len(snapcontPacked)):
				if self.isFnString(snapcontPacked[index][0]):
					expanded = self.getFilesByFN("/proc/sys",snapcontPacked[index][0].replace(".","/"))
					for index2 in range(len(expanded)):
						expandedData = (expanded[index2].replace("/","."),snapcontPacked[index][1])
						snapcont.append(expandedData)
				else:
					snapcont.append(snapcontPacked[index])
			for iopt,ival in snapcont:
				if ival == '':
					tempconfig.set(opt, iopt, out[iopt])
				elif ival == ',,':
					tempconfig.set(opt, iopt, ',,' + out[iopt])
				else:
					reival = ival
					pos = [reival.start() for reival in re.finditer(',', reival)]
					if len(pos) == 2:
						ival = ival[0:pos[1]+1]
						tempconfig.set(opt, iopt, ival + out[iopt])
					else:
						tempconfig.set(opt, iopt, out[iopt])
		snapFileName = self.config['root']+'snapshot' +  strftime("%Y-%m-%d-%H:%M:%S", localtime()) + '.conf'
		try:
			with open(snapFileName , 'w') as configfile:
				tempconfig.write(configfile)
		except IOError:
			print _("Cant save snapshot")
		return snapFileName

	def checkConfigFile(self, filename):
		try:
			msgStack = ''
			if not os.path.exists(filename):
				msgStack = "%s%s %s %s" % (msgStack, _("Error: File"), filename, _("not found\n"))
				return msgStack
			self.checkParser = ConfigParser.RawConfigParser()
			self.checkParser.read(filename)
			for option,value in self.checkParser.items('categories'):
				if not self.checkParser.items(option):
					msgStack = "%s%s %s\n" % (msgStack, _("Error: Enabled section is empty:"), option)
					return msgStack
				current = self.checkParser.items(option)
				for opt,val in current:
					if not os.path.exists("/proc/sys/" + opt.replace(".","/")) and len(self.getFilesByFN("/proc/sys/",opt.replace(".","/"))) == 0:
						msgStack = "%s%s%s\n" % (msgStack, _("Warning: File not found: /proc/sys/"), opt)
					#pos = [val.start() for val in re.finditer(',', val)]
					#if len(pos) > 0 and len(pos) != 2:
					#	msgStack = msgStack + "Error: slider value format is LOW,HIGH,CURRENT. Value: " + opt + "\n"
			return msgStack
		except (ConfigParser.Error, IOError) as e:
			return "Error {0}".format(str(e))

	def isFnString(self, string):
		regMatch = ['[', '*', '?']
		for char in regMatch:
			if char in string:
				return True
		return False

	def getFilesByFN(self, troot, fn):
		mylist = {}
		for root, dirs, files in os.walk(troot, topdown=True):
			for cfile in files:
				if fnmatch.fnmatch(root + "/" + cfile, "*" + fn):
					mylist[len(mylist)] = root.replace(troot,"")[1:] + "/" + cfile
		return mylist
