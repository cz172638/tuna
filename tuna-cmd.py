#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-
#   tuna - Application Tuning GUI
#   Copyright (C) 2008, 2009, 2010, 2011 Red Hat Inc.
#   Arnaldo Carvalho de Melo <acme@redhat.com>
#
#   This application is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; version 2.
#
#   This application is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   General Public License for more details.

import getopt, ethtool, fnmatch, os, procfs, re, schedutils, sys
from tuna import tuna, sysfs

import gettext
import locale

try:
	import inet_diag
	have_inet_diag = True
except:
	have_inet_diag = False

try:
	set
except NameError:
	# In python < 2.4, "set" is not the first class citizen.
	from sets import Set as set

# FIXME: ETOOMANYGLOBALS, we need a class!

nr_cpus = None
ps = None
irqs = None
version = "0.13"

def usage():
	print _('Usage: tuna [OPTIONS]')
	fmt = '\t%-40s %s'
	print fmt % ('-h, --help',		    _('Give this help list'))
	print fmt % ('-a, --config_file_apply=profilename',		    _('Apply changes described in profile'))
	print fmt % ('-l, --config_file_list',		    _('List preloaded profiles'))
	print fmt % ('-g, --gui',		    _('Start the GUI'))
	print fmt % ('-G, --cgroup',		    _('Display the processes with the type of cgroups they are in'))
	print fmt % ('-c, --cpus=' + _('CPU-LIST'), _('%(cpulist)s affected by commands') % \
							{"cpulist": _('CPU-LIST')})
	print fmt % ('-C, --affect_children',	    _('Operation will affect children threads'))
	print fmt % ('-f, --filter',		    _('Display filter the selected entities'))
	print fmt % ('-i, --isolate',		    _('Move all threads away from %(cpulist)s') % \
							{"cpulist": _('CPU-LIST')})
	print fmt % ('-I, --include',		    _('Allow all threads to run on %(cpulist)s') % \
							{"cpulist": _('CPU-LIST')})
	print fmt % ('-K, --no_kthreads',	    _('Operations will not affect kernel threads'))
	print fmt % ('-m, --move',		    _('Move selected entities to %(cpulist)s') % \
							{"cpulist": _('CPU-LIST')})
	print fmt % ('-N, --nohz_full',		    _('CPUs in nohz_full= kernel command line will be affected by operations'))
	if have_inet_diag:
		print fmt % ('-n, --show_sockets',  _('Show network sockets in use by threads'))
	print fmt % ('-p, --priority=[' +
		     _('POLICY') + ':]' +
		     _('RTPRIO'),		    _('Set thread scheduler tunables: %(policy)s and %(rtprio)s') % \
							{"policy": _('POLICY'), "rtprio": _('RTPRIO')})
	print fmt % ('-P, --show_threads',	    _('Show thread list'))
	print fmt % ('-Q, --show_irqs',		    _('Show IRQ list'))
	print fmt % ('-q, --irqs=' + _('IRQ-LIST'), _('%(irqlist)s affected by commands') %
							{"irqlist": _('IRQ-LIST')})
	print fmt % ('-s, --save=' + _('FILENAME'), _('Save kthreads sched tunables to %(filename)s') % \
							{"filename": _('FILENAME')})
	print fmt % ('-S, --sockets=' +
		     _('CPU-SOCKET-LIST'),	    _('%(cpusocketlist)s affected by commands') % \
							{"cpusocketlist": _('CPU-SOCKET-LIST')})
	print fmt % ('-t, --threads=' +
		     _('THREAD-LIST'),		    _('%(threadlist)s affected by commands') % \
							{"threadlist": _('THREAD-LIST')})
	print fmt % ('-U, --no_uthreads',	    _('Operations will not affect user threads'))
	print fmt % ('-v, --version',		    _('Show version'))
	print fmt % ('-W, --what_is',		    _('Provides help about selected entities'))
	print fmt % ('-x, --spread',		    _('Spread selected entities over %(cpulist)s') % \
							{"cpulist": _('CPU-LIST')})

def get_nr_cpus():
	global nr_cpus
	if nr_cpus:
		return nr_cpus
	nr_cpus = procfs.cpuinfo().nr_cpus
	return nr_cpus

nics = None

def get_nics():
	global nics
	if nics:
		return nics
	nics = ethtool.get_active_devices()
	return nics

def thread_help(tid):
	global ps
	if not ps:
		ps = procfs.pidstats()

	if not ps.has_key(tid):
		print "tuna: " + _("thread %d doesn't exists!") % tid
		return

	pinfo = ps[tid]
	cmdline = procfs.process_cmdline(pinfo)
	help, title = tuna.kthread_help_plain_text(tid, cmdline)
	print "%s\n\n%s" % (title, _(help))

def save(cpu_list, thread_list, filename):
	kthreads = tuna.get_kthread_sched_tunings()
	for name in kthreads.keys():
		kt = kthreads[name]
		if (cpu_list and not set(kt.affinity).intersection(set(cpu_list))) or \
		   (thread_list and kt.pid not in thread_list) :
			del kthreads[name]
	tuna.generate_rtgroups(filename, kthreads, get_nr_cpus())

def ps_show_header(has_ctxt_switch_info,cgroups = False):
	print "%7s %6s %5s %7s       %s" % \
		(" ", " ", " ", _("thread"),
		 has_ctxt_switch_info and "ctxt_switches" or "")
	print "%7s %6s %5s %7s%s %15s" % \
		("pid", "SCHED_", "rtpri", "affinity",
		 has_ctxt_switch_info and " %9s %12s" % ("voluntary", "nonvoluntary") or "",
		 "cmd"),
	if cgroups:
		print " %7s" % ("cgroup")
	else:
		print ""

def ps_show_sockets(pid, ps, inodes, inode_re, indent = 0):
	header_printed = False
	dirname = "/proc/%s/fd" % pid
	try:
		filenames = os.listdir(dirname)
	except: # Process died
		return
	sindent = " " * indent
	for filename in filenames:
		pathname = os.path.join(dirname, filename)
		try:
			linkto = os.readlink(pathname)
		except: # Process died
			continue
		inode_match = inode_re.match(linkto)
		if not inode_match:
			continue
		inode = int(inode_match.group(1))
		if not inodes.has_key(inode):
			continue
		if not header_printed:
			print "%s%-10s %-6s %-6s %15s:%-5s %15s:%-5s" % \
			      (sindent, "State", "Recv-Q", "Send-Q",
			       "Local Address", "Port",
			       "Peer Address", "Port")
			header_printed = True
		s = inodes[inode]
		print "%s%-10s %-6d %-6d %15s:%-5d %15s:%-5d" % \
		      (sindent, s.state(),
		       s.receive_queue(), s.write_queue(),
		       s.saddr(), s.sport(), s.daddr(), s.dport())

def format_affinity(affinity):
	if len(affinity) <= 4:
		return ",".join(str(a) for a in affinity)

	return ",".join(str(hex(a)) for a in procfs.hexbitmask(affinity, get_nr_cpus()))

def ps_show_thread(pid, affect_children, ps,
		   has_ctxt_switch_info, sock_inodes, sock_inode_re, cgroups):
	global irqs
	try:
		affinity = format_affinity(schedutils.get_affinity(pid))
	except (SystemError, OSError) as e: # (3, 'No such process') old python-schedutils incorrectly raised SystemError
		if e[0] == 3:
			return
		raise e

	sched = schedutils.schedstr(schedutils.get_scheduler(pid))[6:]
	rtprio = int(ps[pid]["stat"]["rt_priority"])
	cgout = ps[pid]["cgroups"]
	cmd = ps[pid]["stat"]["comm"]
	users = ""
	if tuna.is_irq_thread(cmd):
		try:
			if not irqs:
				irqs = procfs.interrupts()
			if cmd[:4] == "IRQ-":
				users = irqs[tuna.irq_thread_number(cmd)]["users"]
				for u in users:
					if u in get_nics():
						users[users.index(u)] = "%s(%s)" % (u, ethtool.get_module(u))
				users = ",".join(users)
			else:
				u = cmd[cmd.find('-') + 1:]
				if u in get_nics():
					users = ethtool.get_module(u)
		except:
			users = "Not found in /proc/interrupts!"

	ctxt_switch_info = ""
	if has_ctxt_switch_info:
		voluntary_ctxt_switches = int(ps[pid]["status"]["voluntary_ctxt_switches"])
		nonvoluntary_ctxt_switches = int(ps[pid]["status"]["nonvoluntary_ctxt_switches"])
		ctxt_switch_info = " %9d %12s" % (voluntary_ctxt_switches,
						  nonvoluntary_ctxt_switches)
	
	if affect_children:
		print " %-5d " % pid,
	else:
		print "  %-5d" % pid,
	print "%6s %5d %8s%s %15s %s" % (sched, rtprio, affinity,
					 ctxt_switch_info, cmd, users),
	if cgroups:
		print " %9s" % cgout,
	print ""
	if sock_inodes:
		ps_show_sockets(pid, ps, sock_inodes, sock_inode_re,
				affect_children and 3 or 4)
	if affect_children and ps[pid].has_key("threads"):
		for tid in ps[pid]["threads"].keys():
			ps_show_thread(tid, False, ps[pid]["threads"],
				       has_ctxt_switch_info,
				       sock_inodes, sock_inode_re, cgroups)
			

def ps_show(ps, affect_children, thread_list, cpu_list,
	    irq_list_numbers, show_uthreads, show_kthreads,
	    has_ctxt_switch_info, sock_inodes, sock_inode_re, cgroups):
				
	ps_list = []
	for pid in ps.keys():
		iskth = tuna.iskthread(pid)
		if not show_uthreads and not iskth:
			continue
		if not show_kthreads and iskth:
			continue
		in_irq_list = False
		if irq_list_numbers:
			if tuna.is_hardirq_handler(ps, pid):
				try:
					irq = int(ps[pid]["stat"]["comm"][4:])
					if irq not in irq_list_numbers:
						if not thread_list:
							continue
					else:
						in_irq_list = True
				except:
					pass
			elif not thread_list:
				continue
		if not in_irq_list and thread_list and pid not in thread_list:
			continue
		try:
			affinity = schedutils.get_affinity(pid)
		except (SystemError, OSError) as e: # (3, 'No such process') old python-schedutils incorrectly raised SystemError
			if e[0] == 3:
				continue
			raise e
		if cpu_list and not set(cpu_list).intersection(set(affinity)):
			continue
		ps_list.append(pid)

	ps_list.sort()

	for pid in ps_list:
		ps_show_thread(pid, affect_children, ps,
			       has_ctxt_switch_info, sock_inodes,
			       sock_inode_re, cgroups)

def load_socktype(socktype, inodes):
	idiag = inet_diag.create(socktype = socktype)
	while True:
		try:
			s = idiag.get()
		except:
			break
		inodes[s.inode()] = s

def load_sockets():
	inodes = {}
	for socktype in (inet_diag.TCPDIAG_GETSOCK,
			 inet_diag.DCCPDIAG_GETSOCK):
		load_socktype(socktype, inodes)
	return inodes

def do_ps(thread_list, cpu_list, irq_list, show_uthreads,
	  show_kthreads, affect_children, show_sockets, cgroups):
	ps = procfs.pidstats()
	if affect_children:
		ps.reload_threads()

	sock_inodes = None
	sock_inode_re = None
	if show_sockets:
		sock_inodes = load_sockets()
		sock_inode_re = re.compile(r"socket:\[(\d+)\]")
	
	has_ctxt_switch_info = ps[1]["status"].has_key("voluntary_ctxt_switches")
	try:
		if sys.stdout.isatty():
			ps_show_header(has_ctxt_switch_info, cgroups)
		ps_show(ps, affect_children, thread_list,
			cpu_list, irq_list, show_uthreads, show_kthreads,
			has_ctxt_switch_info, sock_inodes, sock_inode_re, cgroups)
	except IOError:
		# 'tuna -P | head' for instance
		pass

def find_drivers_by_users(users):
	nics = get_nics()
	drivers = []
	for u in users:
		try:
			idx = u.index('-')
			u = u[:idx]
		except:
			pass
		if u in nics:
			driver = ethtool.get_module(u)
			if driver not in drivers:
				drivers.append(driver)
		
	return drivers

def show_irqs(irq_list, cpu_list):
	global irqs
	if not irqs:
		irqs = procfs.interrupts()

	if sys.stdout.isatty():
		print "%4s %-16s %8s" % ("#", _("users"), _("affinity"),)
	sorted_irqs = []
	for k in irqs.keys():
		try:
			irqn = int(k)
			affinity = irqs[irqn]["affinity"]
		except:
			continue
		if irq_list and irqn not in irq_list:
			continue

		if cpu_list and not set(cpu_list).intersection(set(affinity)):
			continue
		sorted_irqs.append(irqn)

	sorted_irqs.sort()
	for irq in sorted_irqs:
		affinity = format_affinity(irqs[irq]["affinity"])
		users = irqs[irq]["users"]
		print "%4d %-16s %8s" % (irq, ",".join(users), affinity),
		drivers = find_drivers_by_users(users)
		if drivers:
			print " %s" % ",".join(drivers)
		else:
			print

def do_list_op(op, current_list, op_list):
	if not current_list:
		current_list = []
	if op == '+':
		return list(set(current_list + op_list))
	if op == '-':
		return list(set(current_list) - set(op_list))
	return list(set(op_list))

def thread_mapper(s):
	global ps
	try:
		return [ int(s), ]
	except:
		pass
	if not ps:
		ps = procfs.pidstats()

	try:
		return ps.find_by_regex(re.compile(fnmatch.translate(s)))
	except:
		return ps.find_by_name(s)

def irq_mapper(s):
	global irqs
	try:
		return [ int(s), ]
	except:
		pass
	if not irqs:
		irqs = procfs.interrupts()

	irq_list_str = irqs.find_by_user_regex(re.compile(fnmatch.translate(s)))
	irq_list = []
	for i in irq_list_str:
		try:
			irq_list.append(int(i))
		except:
			pass

	return irq_list

def pick_op(argument):
	if argument[0] in ('+', '-'):
		return (argument[0], argument[1:])
	return (None, argument)

def i18n_init():
	(app, localedir) = ('tuna', '/usr/share/locale')
	locale.setlocale(locale.LC_ALL, '')
	gettext.bindtextdomain(app, localedir)
	gettext.textdomain(app)
	gettext.install(app, localedir)

def apply_config(filename):
	from tuna.config import Config
	config = Config()
	if os.path.exists(filename):
		config.config['root'] = os.getcwd() + "/"
		filename = os.path.basename(filename)
	else:
		if not os.path.exists(config.config['root']+filename):
			print filename + _(" not found!")
			exit(-1)
	if config.loadTuna(filename):
		exit(1)
	ctrl = 0
	values = {}
	values['toapply'] = {}
	for index in range(len(config.ctlParams)):
		for opt in config.ctlParams[index]:
			values['toapply'][ctrl] = {}
			values['toapply'][ctrl]['label'] = opt
			values['toapply'][ctrl]['value'] = config.ctlParams[index][opt]
			ctrl = ctrl + 1
	config.applyChanges(values)

def list_config():
	from tuna.config import Config
	config = Config()
	print _("Preloaded config files:")
	for value in config.populate():
		print value
	exit(1)

def main():
	global ps

	i18n_init()
	try:
		short = "a:c:CfgGhiIKlmNp:PQq:s:S:t:UvWx"
		long = ["cpus=", "affect_children", "filter", "gui", "help",
			"isolate", "include", "no_kthreads", "move", "nohz_full",
			"show_sockets", "priority=", "show_threads",
			"show_irqs", "irqs=",
			"save=", "sockets=", "threads=", "no_uthreads",
			"version", "what_is", "spread","cgroup","config_file_apply=","config_file_list="]
		if have_inet_diag:
			short += "n"
			long.append("show_sockets")
		opts, args = getopt.getopt(sys.argv[1:], short, long)
	except getopt.GetoptError, err:
		usage()
		print str(err)
		sys.exit(2)

	run_gui = not opts
	kthreads = True
	uthreads = True
	cgroups = False
	cpu_list = None
	irq_list = None
	irq_list_str = None
	thread_list = []
	thread_list_str = None
	filter = False
	affect_children = False
	show_sockets = False

	for o, a in opts:
		if o in ("-h", "--help"):
			usage()
			return
		elif o in ("-a", "--config_file_apply"):
			apply_config(a)
		elif o in ("-l", "--config_file_list"):
			list_config()
		elif o in ("-c", "--cpus"):
			(op, a) = pick_op(a)
			op_list = tuna.cpustring_to_list(a)
			cpu_list = do_list_op(op, cpu_list, op_list)
		elif o in ("-N", "--nohz_full"):
			try:
				cpu_list = tuna.nohz_full_list()
			except:
				print "tuna: --nohz_full " + _(" needs nohz_full=cpulist on the kernel command line")
				sys.exit(2)
		elif o in ("-C", "--affect_children"):
			affect_children = True
		elif o in ("-G", "--cgroup"):
			cgroups = True
		elif o in ("-t", "--threads"):
			(op, a) = pick_op(a)
			op_list = reduce(lambda i, j: i + j,
					 map(thread_mapper, a.split(",")))
			op_list = list(set(op_list))
			thread_list = do_list_op(op, thread_list, op_list)
			# Check if a process name was especified and no
			# threads was found, which would result in an empty
			# thread list, i.e. we would print all the threads
			# in the system when we should print nothing.
			if not op_list and type(a) == type(''):
				thread_list_str = do_list_op(op, thread_list_str,
							     a.split(","))
			if not op:
				irq_list = None
		elif o in ("-f", "--filter"):
			filter = True
		elif o in ("-g", "--gui"):
			run_gui = True
		elif o in ("-i", "--isolate"):
			if not cpu_list:
				print "tuna: --isolate " + _("requires a cpu list!")
				sys.exit(2)
			tuna.isolate_cpus(cpu_list, get_nr_cpus())
		elif o in ("-I", "--include"):
			if not cpu_list:
				print "tuna: --include " + _("requires a cpu list!")
				sys.exit(2)
			tuna.include_cpus(cpu_list, get_nr_cpus())
		elif o in ("-p", "--priority"):
			if not thread_list:
				print ("tuna: %s " % o) + _("requires a thread list!")
				sys.exit(2)
			try:
				tuna.threads_set_priority(thread_list, a, affect_children)
			except (SystemError, OSError) as err: # (3, 'No such process') old python-schedutils incorrectly raised SystemError
				print "tuna: %s" % err
				sys.exit(2)
		elif o in ("-P", "--show_threads"):
			# If the user specified process names that weren't
			# resolved to pids, don't show all threads.
			if not thread_list and not irq_list:
				if thread_list_str or irq_list_str:
					continue
			do_ps(thread_list, cpu_list, irq_list, uthreads,
			      kthreads, affect_children, show_sockets, cgroups)
		elif o in ("-Q", "--show_irqs"):
			# If the user specified IRQ names that weren't
			# resolved to IRQs, don't show all IRQs.
			if not irq_list and irq_list_str:
				continue
			show_irqs(irq_list, cpu_list)
		elif o in ("-n", "--show_sockets"):
			show_sockets = True
		elif o in ("-m", "--move", "-x", "--spread"):
			if not cpu_list:
				print "tuna: --move " + _("requires a cpu list!")
				sys.exit(2)
			if not (thread_list or irq_list):
				print "tuna: --move " + _("requires a list of threads/irqs!")
				sys.exit(2)

			spread = o in ("-x", "--spread")

			if thread_list:
				tuna.move_threads_to_cpu(cpu_list, thread_list,
							 spread = spread)

			if irq_list:
				tuna.move_irqs_to_cpu(cpu_list, irq_list,
						      spread = spread)
		elif o in ("-s", "--save"):
			save(cpu_list, thread_list, a)
		elif o in ("-S", "--sockets"):
			(op, a) = pick_op(a)
			sockets = map(lambda socket: socket, a.split(","))

			if not cpu_list:
				cpu_list = []

			cpu_info = sysfs.cpus()
			op_list = []
			for socket in sockets:
				if not cpu_info.sockets.has_key(socket):
					print "tuna: %s" % \
					      (_("invalid socket %(socket)s sockets available: %(available)s") % \
					      {"socket": socket,
					       "available": ",".join(cpu_info.sockets.keys())})
					sys.exit(2)
				op_list += [ int(cpu.name[3:]) for cpu in cpu_info.sockets[socket] ]
			cpu_list = do_list_op(op, cpu_list, op_list)
		elif o in ("-K", "--no_kthreads"):
			kthreads = False
		elif o in ("-q", "--irqs"):
			(op, a) = pick_op(a)
			op_list = reduce(lambda i, j: i + j,
					 map(irq_mapper, list(set(a.split(",")))))
			irq_list = do_list_op(op, irq_list, op_list)
			# See comment above about thread_list_str
			if not op_list and type(a) == type(''):
				irq_list_str = do_list_op(op, irq_list_str,
							  a.split(","))
			if not op:
				thread_list = []
			if not ps:
				ps = procfs.pidstats()
			if tuna.has_threaded_irqs(ps):
				for irq in irq_list:
					irq_re = tuna.threaded_irq_re(irq)
					irq_threads = ps.find_by_regex(irq_re)
					if irq_threads:
						# Change the affinity of the thread too
						# as we can't rely on changing the irq
						# affinity changing the affinity of the
						# thread or vice versa. We need to change
						# both.
						thread_list += irq_threads

		elif o in ("-U", "--no_uthreads"):
			uthreads = False
		elif o in ("-v", "--version"):
			print version
		elif o in ("-W", "--what_is"):
			if not thread_list:
				print "tuna: --what_is " + _("requires a thread list!")
				sys.exit(2)
			for tid in thread_list:
				thread_help(tid)

	if run_gui:
		try:
			from tuna import tuna_gui
		except ImportError:
			# gui packages not installed
			print _('tuna: packages needed for the GUI missing.')
			print _('      Make sure xauth, pygtk2-libglade are installed.')
			usage()
			return
		except RuntimeError:
			print "tuna: machine needs to be authorized via xhost or ssh -X?"
			return

		try:
			cpus_filtered = filter and cpu_list or []
			app = tuna_gui.main_gui(kthreads, uthreads, cpus_filtered)
			app.run()
		except KeyboardInterrupt:
			pass

if __name__ == '__main__':
    main()
