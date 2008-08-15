#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import os

class cpu:
	def __init__(self, basedir, name):
		self.name = name
		self.dir = "%s/%s" % (basedir, name)
		self.reload()

	def readfile(self, name):
		try:
			f = open("%s/%s" % (self.dir, name))
			value = f.readline().strip()
			f.close()
		except:
			raise
		return value

	def reload_online(self):
		self.online = True
		try:
			self.online = self.readfile("online") == "1"
		except:
			# boot CPU, usually cpu0, can't be brought offline, so
			# lacks the file and non root users can't read. In both
			# cases assume CPU is online.
			pass

	def reload(self):
		self.reload_online()
		if self.online:
			self.physical_package_id = self.readfile("topology/physical_package_id")
		else:
			self.physical_package_id = None

	def set_online(self, online = True):
		try:
			f = open("%s/online" % self.dir, "w")
			f.write("%d\n" % (online and 1 or 0))
			f.close()
		except:
			pass

		self.reload_online()
		return online == self.online

class cpus:
	def __init__(self, basedir = "/sys/devices/system/cpu"):
		self.basedir = basedir
		self.cpus = {}
		self.sockets = {}
		self.reload()
		self.nr_cpus = len(self.cpus)

	def __getitem__(self, key):
		return self.cpus[key]

	def keys(self):
		return self.cpus.keys()

	def has_key(self, key):
		return self.cpus.has_key(key)

	def reload(self):
		for name in os.listdir(self.basedir):
			if name[:3] != "cpu" or not name[3].isdigit():
				continue

			if name in self.cpus:
				self.cpus[name].reload(self.basedir)
			else:
				c = cpu(self.basedir, name)
				self.cpus[name] = c
				socket = c.physical_package_id
				if socket in self.sockets:
					self.sockets[socket].insert(0, c)
				else:
					self.sockets[socket] = [ c, ]

if __name__ == '__main__':
	import sys

	cpus = cpus()

	for socket in cpus.sockets.keys():
		print "Socket %s" % socket
		for c in cpus.sockets[socket]:
			print "  %s" % c.name
			print "    online: %s" % c.online
			c.set_online(False)
			print "    online: %s" % c.online
			c.set_online()
			print "    online: %s" % c.online
