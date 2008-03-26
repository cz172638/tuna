#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-
#   tuna - Application Tuning Gru
#   Copyright (C) 2008 Red Hat Inc.
#
#   This application is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; version 2.
#
#   This application is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   General Public License for more details.

import getopt, procfs, sys, tuna

nr_cpus = None

def usage():
	print '''Usage: tuna [OPTIONS]
	-h, --help             Give this help list
	-g, --gui              Start the GUI
	-i, --isolate_cpu=CPU  Move all threads away from CPU'''

def gui():
	try:
		app = tuna.tuna()
		app.run()
	except KeyboardInterrupt:
		pass

def get_nr_cpus():
	global nr_cpus
	if nr_cpus:
		return nr_cpus
	nr_cpus = procfs.cpuinfo().nr_cpus
	return nr_cpus

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:],
					   "i:gh",
					   ( "isolate_cpus=", "gui", "help", ))
	except getopt.GetoptError, err:
		usage()
		print str(err)
		sys.exit(2)

	if not opts:
		gui()
		return

	for o, a in opts:
		if o in ("-h", "--help"):
			usage()
			return
		elif o in ("-g", "--gui"):
			gui()
			return
		elif o in ("-i", "--isolate_cpus"):
			tuna.isolate_cpu(int(a), get_nr_cpus())

if __name__ == '__main__':
    main()
