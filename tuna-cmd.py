#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-
#   tuna - Application Tuning GUI
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

import getopt, ethtool, procfs, schedutils, sys
from tuna import tuna, sysfs

try:
	from sets import Set as set
except:
	# OK, we're modern, having sets as first class citizens
	pass

# FIXME: ETOOMANYGLOBALS, we need a class!

nr_cpus = None
ps = None

def usage():
	print '''Usage: tuna [OPTIONS]
	-h, --help			Give this help list
	-g, --gui			Start the GUI
	-c, --cpus=CPU-LIST		CPU-LIST affected by commands
	-C, --affect_children		Operation will affect children threads
	-f, --filter			Display filter the selected entities
	-i, --isolate			Move all threads away from CPU-LIST
	-I, --include			Allow all threads to run on CPU-LIST
	-K, --no_kthreads		Operations will not affect kernel threads
	-m, --move			move selected entities to CPU-LIST
	-p, --priority=[POLICY]:RTPRIO	set thread scheduler POLICY and RTPRIO
	-P, --show_threads		show thread list
	-s, --save=FILENAME		save kthreads sched tunables to FILENAME
	-S, --sockets=CPU-SOCKET-LIST   CPU-SOCKET-LIST affected by commands
	-t, --threads=THREAD-LIST	THREAD-LIST affected by commands
	-U, --no_uthreads		Operations will not affect user threads
	-W, --what_is			Provides help about selected entities'''

def get_nr_cpus():
	global nr_cpus
	if nr_cpus:
		return nr_cpus
	nr_cpus = procfs.cpuinfo().nr_cpus
	return nr_cpus

def thread_help(tid):
	global ps
	if not ps:
		ps = procfs.pidstats()

	if not ps.has_key(tid):
		print "tuna: thread %d doesn't exists!" % tid
		return

	pinfo = ps[tid]
	cmdline = procfs.process_cmdline(pinfo)
	help, title = tuna.kthread_help_plain_text(tid, cmdline)
	print "%s\n\n%s" % (title, help)

def save(cpus, threads, filename):
	kthreads = tuna.get_kthread_sched_tunings()
	for name in kthreads.keys():
		kt = kthreads[name]
		if (cpus and not set(kt.affinity).intersection(set(cpus))) or \
		   (threads and kt.pid not in threads) :
			del kthreads[name]
	tuna.generate_rtgroups(filename, kthreads, get_nr_cpus())

def ps_show_header(has_ctxt_switch_info):
	print "%7s %6s %5s %7s       %s" % \
		(" ", " ", " ", "thread",
		 has_ctxt_switch_info and "ctxt_switches" or "")
	print "%7s %6s %5s %7s%s %15s" % \
		("pid", "SCHED_", "rtpri", "affinity",
		 has_ctxt_switch_info and " %9s %12s" % ("voluntary", "nonvoluntary") or "",
		 "cmd")

def ps_show_thread(pid, affect_children, ps, cpuinfo, irqs, nics, has_ctxt_switch_info):
	affinity = schedutils.get_affinity(pid)
	if len(affinity) <= 4:
		affinity = ",".join(str(a) for a in affinity)
	else:
		affinity = ",".join(str(hex(a)) for a in procfs.hexbitmask(affinity, cpuinfo.nr_cpus))
	sched = schedutils.schedstr(schedutils.get_scheduler(pid))[6:]
	rtprio = int(ps[pid]["stat"]["rt_priority"])
	cmd = ps[pid]["stat"]["comm"]
	users = ""
	if cmd[:4] == "IRQ-":
		try:
			users = irqs[cmd[4:]]["users"]
			for u in users:
				if u in nics:
					users[users.index(u)] = "%s(%s)" % (u, ethtool.get_module(u))
			users = ",".join(users)
		except:
			users = "Not found in /proc/interrupts!"

	ctxt_switch_info = ""
	if has_ctxt_switch_info:
		voluntary_ctxt_switches = int(ps[pid]["status"]["voluntary_ctxt_switches"])
		nonvoluntary_ctxt_switches = int(ps[pid]["status"]["nonvoluntary_ctxt_switches"])
		ctxt_switch_info = " %9d %12s" % (voluntary_ctxt_switches,
						  nonvoluntary_ctxt_switches)
	
	if affect_children:
		print "%6d " % pid,
	else:
		print "  %5d" % pid,
	print "%6s %5d %8s%s %15s %s" % (sched, rtprio, affinity,
					 ctxt_switch_info, cmd, users)
	if affect_children and ps[pid].has_key("threads"):
		for tid in ps[pid]["threads"].keys():
			ps_show_thread(tid, False, ps[pid]["threads"],
				       cpuinfo, irqs, nics,
				       has_ctxt_switch_info)
			

def ps_show(ps, affect_children, cpuinfo, irqs, threads, cpus,
	    show_uthreads, show_kthreads, has_ctxt_switch_info):

	ps_list = []
	for pid in ps.keys():
		if threads and pid not in threads:
			continue
		iskth = tuna.iskthread(pid)
		if not show_uthreads and not iskth:
			continue
		if not show_kthreads and iskth:
			continue
		affinity = schedutils.get_affinity(pid)
		if cpus and not set(cpus).intersection(set(affinity)):
			continue
		ps_list.append(pid)

	ps_list.sort()

	nics = ethtool.get_active_devices()

	for pid in ps_list:
		ps_show_thread(pid, affect_children, ps, cpuinfo, irqs, nics, has_ctxt_switch_info)

def ps(threads, cpus, show_uthreads, show_kthreads, affect_children):
	ps = procfs.pidstats()
	if affect_children:
		ps.reload_threads()
	cpuinfo = procfs.cpuinfo()
	irqs = procfs.interrupts()
	has_ctxt_switch_info = ps[1]["status"].has_key("voluntary_ctxt_switches")
	ps_show_header(has_ctxt_switch_info)
	ps_show(ps, affect_children, cpuinfo, irqs, threads, cpus,
		show_uthreads, show_kthreads, has_ctxt_switch_info)

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:],
					   "c:CfghiIKmp:Ps:S:t:UW",
					   ("cpus=", "affect_children",
					    "filter", "gui", "help",
					    "isolate", "include",
					    "no_kthreads",
					    "move", "priority", "show_threads",
					    "save=", "sockets=", "threads=",
					    "no_uthreads", "what_is"))
	except getopt.GetoptError, err:
		usage()
		print str(err)
		sys.exit(2)

	run_gui = not opts
	kthreads = True
	uthreads = True
	cpus = None
	threads = None
	filter = False
	affect_children = False

	for o, a in opts:
		if o in ("-h", "--help"):
			usage()
			return
		elif o in ("-c", "--cpus"):
			cpus = map(lambda cpu: int(cpu), a.split(","))
		elif o in ("-C", "--affect_children"):
			affect_children = True
		elif o in ("-t", "--threads"):
			threads = map(lambda cpu: int(cpu), a.split(","))
		elif o in ("-f", "--filter"):
			filter = True
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
			tuna.include_cpus(cpus, get_nr_cpus())
		elif o in ("-p", "--priority"):
			tuna.threads_set_priority(threads, a, affect_children)
		elif o in ("-P", "--show_threads"):
			ps(threads, cpus, uthreads, kthreads, affect_children)
		elif o in ("-m", "--move"):
			if not cpus:
				print "tuna: --move requires a cpu list!"
				sys.exit(2)
			if not threads:
				print "tuna: --move requires a thread list!"
				sys.exit(2)
			tuna.move_threads_to_cpu(cpus, threads)
		elif o in ("-s", "--save"):
			save(cpus, threads, a)
		elif o in ("-S", "--sockets"):
			sockets = map(lambda socket: socket, a.split(","))
			if not cpus:
				cpus = []
			cpu_info = sysfs.cpus()
			for socket in sockets:
				if not cpu_info.sockets.has_key(socket):
					print "tuna: invalid socket %s, sockets available: %s" % \
					      (socket,
					       ", ".join(cpu_info.sockets.keys()))
					sys.exit(2)
				cpus += [ int(cpu.name[3:]) for cpu in cpu_info.sockets[socket] ]
			cpus.sort()
		elif o in ("-K", "--no_kthreads"):
			kthreads = False
		elif o in ("-U", "--no_uthreads"):
			uthreads = False
		elif o in ("-W", "--what_is"):
			if not threads:
				print "tuna: --what_is requires a thread list!"
				sys.exit(2)
			for tid in threads:
				thread_help(tid)

	if run_gui:
		try:
			from tuna import tuna_gui
		except ImportError:
			# gui packages not installed
			usage()
			return
		try:
			cpus_filtered = filter and cpus or []
			app = tuna_gui.gui(kthreads, uthreads, cpus_filtered)
			app.run()
		except KeyboardInterrupt:
			pass

if __name__ == '__main__':
    main()
