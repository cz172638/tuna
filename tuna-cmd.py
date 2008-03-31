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
	-h, --help			Give this help list
	-g, --gui			Start the GUI
	-c, --cpus=CPU-LIST		CPU-LIST affected by commands
	-i, --isolate			Move all threads away from CPU-LIST
	-I, --include			Allow all threads to run on CPU-LIST
	-K, --no_kthreads		Operations will not affect kernel threads
	-m, --move			move selected entities to CPU-LIST
	-t, --threads=THREAD-LIST	THREAD-LIST affected by commands
	-U, --no_uthreads		Operations will not affect user threads'''

def gui(kthreads = True, uthreads = True):
	try:
		app = tuna.tuna(kthreads, uthreads)
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
					   "c:ghiIKmt:U",
					   ("cpus=", "gui", "help",
					    "isolate", "include",
					    "no_kthreads",
					    "move", "threads=",
					    "no_uthreads"))
	except getopt.GetoptError, err:
		usage()
		print str(err)
		sys.exit(2)

	if not opts:
		gui()
		return
	
	run_gui = False
	kthreads = True
	uthreads = True
	cpus = None
	threads = None

	for o, a in opts:
		if o in ("-h", "--help"):
			usage()
			return
		elif o in ("-c", "--cpus"):
			cpus = map(lambda cpu: int(cpu), a.split(","))
		elif o in ("-t", "--threads"):
			threads = map(lambda cpu: int(cpu), a.split(","))
		elif o in ("-g", "--gui"):
			run_gui = True
		elif o in ("-i", "--isolate"):
			if not cpus:
				print "tuna: --isolate requires a cpu list!"
				sys.exit(2)
			tuna.isolate_cpus(cpus, get_nr_cpus())
		elif o in ("-I", "--include"):
			if not cpus:
				print "tuna: --include requires a cpu list!"
				sys.exit(2)
			for cpu in cpus:
				tuna.include_cpu(cpu, get_nr_cpus())
		elif o in ("-m", "--move"):
			if not cpus:
				print "tuna: --move requires a cpu list!"
				sys.exit(2)
			if not threads:
				print "tuna: --move requires a thread list!"
				sys.exit(2)
			tuna.move_threads_to_cpu(cpus, threads)
		elif o in ("-K", "--no_kthreads"):
			kthreads = False
		elif o in ("-U", "--no_uthreads"):
			uthreads = False

	if run_gui:
		gui(kthreads, uthreads)

if __name__ == '__main__':
    main()
