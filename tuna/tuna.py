#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import copy, ethtool, os, procfs, schedutils

try:
	from sets import Set as set
except:
	# OK, we're modern, having sets as first class citizens
	pass

kthread_help_str = {}

def kthread_help(key):
	if kthread_help_str.has_key(key):
		help = kthread_help_str[key]
	else:
		orig_key = key
		if key[-1:] == '/':
			key = "%s-" % key[:-1]
		helpfile1 = "/usr/share/tuna/help/kthreads/%s" % key
		helpfile2 = "help/kthreads/%s" % key
		try: 
			f = file(helpfile1)
		except:
			try:
				f = file(helpfile2)
			except:
				return ""

		help = reduce(lambda a, b: a + b, f.readlines())
		f.close()
		kthread_help_str[orig_key] = help
	return help

def kthread_help_plain_text(pid, cmdline):
	cmdline = cmdline.split(' ')[0]
	if iskthread(pid):
		try:
			index = cmdline.index("/")
			key = cmdline[:index + 1]
			suffix_help = "\nOne per CPU"
		except:
			key = cmdline
			suffix_help = ""
		help = kthread_help(key)
		title = "Kernel Thread %d (%s):" % (pid, cmdline)
		help += suffix_help
	else:
		title = "User Thread %d (%s):" % (pid, cmdline)
		help = title

	return help, title

# Zombies also doesn't have smaps entries, but it should be good enough
def iskthread(pid):
	try:
		f = file("/proc/%d/smaps" % pid)
	except IOError:
		# Thread has vanished
		return True

	line = f.readline()
	f.close()
	return not line

# FIXME: Move to python-linux-procfs
def has_threaded_irqs(irqs, ps):
	for sirq in irqs.keys():
		try:
			irq = int(sirq)
			if ps.find_by_name("IRQ-%d" % irq):
				return True
		except:
			pass
	return False

def set_irq_affinity(irq, bitmasklist):
	text = ",".join(map(lambda a: "%x" % a, bitmasklist))
	f = file("/proc/irq/%d/smp_affinity" % irq, "w")
	f.write("%s\n" % text)
	try:
		f.close()
	except IOError:
		# This happens with IRQ 0, for instance
		return False
	return True

def cpustring_to_list(cpustr):
	"""Convert a string of numbers to an integer list.
    
	Given a string of comma-separated numbers and number ranges,
	return a simple sorted list of the integers it represents.

	This function will throw exceptions for badly-formatted strings.
    
	Returns a list of integers."""

	fields = cpustr.strip().split(",")
	cpu_list = []
	for field in fields:
		ends = field.split("-")
		if len(ends) > 2:
			raise "Syntax error"
		if len(ends) == 2:
			cpu_list += range(int(ends[0]), int(ends[1])+1)
		else:
			cpu_list += [int(ends[0])]
	return list(set(cpu_list))

def list_to_cpustring(l):
	"""Convert a list of integers into a range string.

	Consecutive values will be collapsed into ranges.

	This should not throw any exceptions as long as the list is all
	positive integers.

	Returns a string."""

	l = list(set(l))
	strings = []
	inrange = False
	prev = -2
	while len(l):
		i = l.pop(0)
		if i - 1 == prev:
			while len(l):
				j = l.pop(0)
				if j - 1 != i:
					l.insert(0, j)
					break;
				i = j
			t = strings.pop()
			if int(t) + 1 == i:
				strings.append("%s,%u" % (t, i))
			else:
				strings.append("%s-%u" % (t, i))
		else:
			strings.append("%u" % i)
		prev = i
	return ",".join(strings)

def move_threads_to_cpu(new_affinity, pid_list):
	changed = False

	ps = procfs.pidstats()
	for pid in pid_list:
		try:
			curr_affinity = schedutils.get_affinity(pid)
			if curr_affinity != new_affinity:
				schedutils.set_affinity(pid, new_affinity)
				curr_affinity = schedutils.get_affinity(pid)
				if curr_affinity == new_affinity:
					changed = True
				else:
					set_affinity_warning(pid, new_affinity)

			# See if this is the thread group leader
			if not ps.has_key(pid):
				continue

			threads = procfs.pidstats("/proc/%d/task" % pid)
			for tid in threads.keys():
				curr_affinity = schedutils.get_affinity(tid)
				if curr_affinity != new_affinity:
					schedutils.set_affinity(tid, new_affinity)
					curr_affinity = schedutils.get_affinity(tid)
					if curr_affinity == new_affinity:
						changed = True
					else:
						set_affinity_warning(tid, new_affinity)
		except SystemError:
			# process died
			continue
	return changed

def affinity_remove_cpus(affinity, cpus, nr_cpus):
	# If the cpu being isolated was the only one in the current affinity
	affinity = list(set(affinity) - set(cpus))
	if not affinity:
		affinity = range(nr_cpus)
		affinity = list(set(affinity) - set(cpus))
	return affinity

def isolate_cpus(cpus, nr_cpus):
	ps = procfs.pidstats()
	ps.reload_threads()
	previous_pid_affinities = {}
	for pid in ps.keys():
		if iskthread(pid):
			continue
		affinity = schedutils.get_affinity(pid)
		if set(affinity).intersection(set(cpus)):
			previous_pid_affinities[pid] = copy.copy(affinity)
			affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
			schedutils.set_affinity(pid, affinity)

		if not ps[pid].has_key("threads"):
			continue
		threads = ps[pid]["threads"]
		for tid in threads.keys():
			if iskthread(tid):
				continue
			affinity = schedutils.get_affinity(tid)
			if set(affinity).intersection(set(cpus)):
				previous_pid_affinities[tid] = copy.copy(affinity)
				affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
				schedutils.set_affinity(tid, affinity)

	del ps

	# Now isolate it from IRQs too
	irqs = procfs.interrupts()
	previous_irq_affinities = {}
	for irq in irqs.keys():
		# LOC, NMI, TLB, etc
		if not irqs[irq].has_key("affinity"):
			continue
		affinity = irqs[irq]["affinity"]
		if set(affinity).intersection(set(cpus)):
			previous_irq_affinities[irq] = copy.copy(affinity)
			affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
			set_irq_affinity(int(irq),
					 procfs.hexbitmask(affinity,
							   nr_cpus))

	return (previous_pid_affinities, previous_irq_affinities)

def include_cpu(cpu, nr_cpus):
	ps = procfs.pidstats()
	ps.reload_threads()
	previous_pid_affinities = {}
	for pid in ps.keys():
		if iskthread(pid):
			continue
		affinity = schedutils.get_affinity(pid)
		if cpu not in affinity:
			previous_pid_affinities[pid] = copy.copy(affinity)
			affinity.append(cpu)
			schedutils.set_affinity(pid, affinity)

		if not ps[pid].has_key("threads"):
			continue
		threads = ps[pid]["threads"]
		for tid in threads.keys():
			if iskthread(tid):
				continue
			affinity = schedutils.get_affinity(tid)
			if cpu not in affinity:
				previous_pid_affinities[tid] = copy.copy(affinity)
				affinity.append(cpu)
				schedutils.set_affinity(tid, affinity)

	del ps

	# Now include it in IRQs too
	irqs = procfs.interrupts()
	previous_irq_affinities = {}
	for irq in irqs.keys():
		# LOC, NMI, TLB, etc
		if not irqs[irq].has_key("affinity"):
			continue
		affinity = irqs[irq]["affinity"]
		if cpu not in affinity:
			previous_irq_affinities[irq] = copy.copy(affinity)
			affinity.append(cpu)
			set_irq_affinity(int(irq),
					 procfs.hexbitmask(affinity, nr_cpus))

	return (previous_pid_affinities, previous_irq_affinities)

def get_irq_users(irqs, irq, nics = None):
	if not nics:
		nics = ethtool.get_active_devices()
	users = irqs[irq]["users"]
	for u in users:
		if u in nics:
			try:
				users[users.index(u)] = "%s(%s)" % (u, ethtool.get_module(u))
			except IOError:
				# Old kernel, doesn't implement ETHTOOL_GDRVINFO
				pass
	return users

def get_irq_affinity_text(irqs, irq):
	affinity_list = irqs[irq]["affinity"]
	try:
		return list_to_cpustring(affinity_list)
	except:
		# needs root prio to read /proc/irq/<NUM>/smp_affinity
		return ""

def thread_filtered(tid, cpus_filtered, show_kthreads, show_uthreads):
	if cpus_filtered:
		affinity = schedutils.get_affinity(tid)
		if set(cpus_filtered + affinity) == set(cpus_filtered):
			return True

	if not (show_kthreads and show_uthreads):
		kthread = iskthread(tid)
		if ((not show_kthreads) and kthread) or \
		   ((not show_uthreads) and not kthread):
			return True

	return False

def irq_filtered(irq, irqs, cpus_filtered, is_root):
	if cpus_filtered and is_root:
		affinity = irqs[irq]["affinity"]
		if set(cpus_filtered + affinity) == set(cpus_filtered):
			return True

	return False

def thread_set_priority(tid, policy, rtprio):
	if not policy and policy != 0:
		policy = schedutils.get_scheduler(tid)
	schedutils.set_scheduler(tid, policy, rtprio)

def threads_set_priority(tids, parm, affect_children = False):
	parms = parm.split(":")
	policy = None
	if len(parms) != 1:
		policy = schedutils.schedfromstr("SCHED_%s" % parms[0].upper())
		rtprio = int(parms[1])
	else:
		rtprio = int(parms[0])

	for tid in tids:
		thread_set_priority(tid, policy, rtprio)
		if affect_children:
			for child in [int (a) for a in os.listdir("/proc/%d/task" % tid)]:
				if child != tid:
					thread_set_priority(child, policy, rtprio)

class sched_tunings:
	def __init__(self, name, pid, policy, rtprio, affinity, percpu):
		self.name = name
		self.pid = pid
		self.policy = policy
		self.rtprio = int(rtprio)
		self.affinity = affinity
		self.percpu = percpu

def get_kthread_sched_tunings(proc = None):
	if not proc:
		proc = procfs.pidstats()

	kthreads = {}
	for pid in proc.keys():
		if iskthread(pid):
			name = proc[pid]["stat"]["comm"]
			rtprio = int(proc[pid]["stat"]["rt_priority"])
			policy = schedutils.get_scheduler(pid)
			affinity = schedutils.get_affinity(pid)
			percpu = iskthread(pid) and \
				 proc.is_bound_to_cpu(pid)
			kthreads[name] = sched_tunings(name, pid, policy,
						       rtprio, affinity,
						       percpu)

	return kthreads

def generate_rtgroups(filename, kthreads, nr_cpus):
	f = file(filename, "w")
	f.write('''# Generated by tuna
#
# Use it with rtctl:
# 
# rtctl --file %s reset
#
# Please use 'man rtctl' for more operations
#
# Associate processes into named groups with default priority and 
# scheduling policy.
#
# Format is: <groupname>:<sched>:<prio>:<regex>
#
# groupname must start at beginning of line.
# sched must be one of: 'f' (fifo)
#                       'b' (batch)
#                       'r' (round-robin)
#                       'o' (other) 
#                       '*' (leave alone)
# regex is an awk regex
#
# The regex is matched against process names as printed by "ps -eo cmd".

''' % filename)
	f.write("kthreads:*:1:*:\[.*\]$\n\n")

	per_cpu_kthreads = []
	names = kthreads.keys()
	names.sort()
	for name in names:
		kt = kthreads[name]
		try:
			idx = name.index("/")
			common = name[:idx]
			if common in per_cpu_kthreads:
				continue
			per_cpu_kthreads.append(common)
			name = common
			if common[:5] == "sirq-":
				common = "(sirq|softirq)" + common[4:]
			elif common[:8] == "softirq-":
				common = "(sirq|softirq)" + common[7:]
				name = "s" + name[4:]
			regex = common + "\/.*" 
		except:
			idx = 0
			regex = name
			pass
		if kt.percpu or idx != 0:
			# Don't mess with workqueues, etc
			mask = "*"
		else:
			mask = ",".join([hex(a) for a in \
					 procfs.hexbitmask(kt.affinity, nr_cpus)])
		f.write("%s:%c:%d:%s:\[%s\]$\n" % (name,
						   schedutils.schedstr(kt.policy)[6].lower(),
						   kt.rtprio, mask, regex))
	f.close()
