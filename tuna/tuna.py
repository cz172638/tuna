# -*- python -*-
# -*- coding: utf-8 -*-

import copy, ethtool, errno, os, procfs, re, schedutils, sys, shlex
from . import help
import fnmatch
from procfs import utilist

try:
        set
except NameError:
        from sets import Set as set

try:
        fntable
except NameError:
        fntable = []

def kthread_help(key):
        if '/' in key:
                key = key[:key.rfind('/')+1]
        return help.KTHREAD_HELP.get(key, " ")

def proc_sys_help(key):
        if not len(fntable):
                regMatch = ['[', '*', '?']
                for value in help.PROC_SYS_HELP:
                        for char in regMatch:
                                if char in value:
                                        fntable.append(value)
        temp = help.PROC_SYS_HELP.get(key, "")
        if len(temp):
                return key + ":\n" + temp
        else:
                for value in fntable:
                        if fnmatch.fnmatch(key, value):
                                return key + ":\n" + help.PROC_SYS_HELP.get(value, "")
                return key

def kthread_help_plain_text(pid, cmdline):
        cmdline = cmdline.split(' ')[0]
        params = {'pid':pid, 'cmdline':cmdline}

        if iskthread(pid):
                title = _("Kernel Thread %(pid)d (%(cmdline)s):") % params
                help = kthread_help(cmdline)
        else:
                title = _("User Thread %(pid)d (%(cmdline)s):") % params
                help = title

        return help, title

def iskthread(pid):
        # FIXME: we should leave to the callers to handle all the exceptions,
        # in this function, so that they know that the thread vanished and
        # can act accordingly, removing entries from tree views, etc
        try:
                f = open("/proc/%d/smaps" % pid)
        except IOError:
                # Thread has vanished
                return True

        line = f.readline()
        f.close()
        if line:
                return False
        # Zombies also doesn't have smaps entries, so check the
        # state:
        try:
                p = procfs.pidstat(pid)
        except:
                return True
        
        if p["state"] == 'Z':
                return False
        return True
        
def irq_thread_number(cmd):
        if cmd[:4] == "irq/":
                return cmd[4:cmd.find('-')]
        elif cmd[:4] == "IRQ-":
                return cmd[4:]
        else:
                raise LookupError

def is_irq_thread(cmd):
        return cmd[:4] in ("IRQ-", "irq/")

def threaded_irq_re(irq):
        return re.compile("(irq/%s-.+|IRQ-%s)" % (irq, irq))

# FIXME: Move to python-linux-procfs
def has_threaded_irqs(ps):
        irq_re = re.compile("(irq/[0-9]+-.+|IRQ-[0-9]+)")
        return len(ps.find_by_regex(irq_re)) > 0

def set_irq_affinity_filename(filename, bitmasklist):
        pathname="/proc/irq/%s" % filename
        f = open(pathname, "w")
        text = ",".join(["%x" % a for a in bitmasklist])
        f.write("%s\n" % text)
        try:
                f.close()
        except IOError:
                # This happens with IRQ 0, for instance
                return False
        return True

def set_irq_affinity(irq, bitmasklist):
        return set_irq_affinity_filename("%d/smp_affinity" % irq, bitmasklist)

def cpustring_to_list(cpustr):
        """Convert a string of numbers to an integer list.
    
        Given a string of comma-separated numbers and number ranges,
        return a simple sorted list of the integers it represents.

        This function will throw exceptions for badly-formatted strings.
    
        Returns a list of integers."""

        fields = cpustr.strip().split(",")
        cpu_list = []
        for field in fields:
                ends = [ int(a, 0) for a in field.split("-") ]
                if len(ends) > 2:
                        raise SyntaxError("Syntax error")
                if len(ends) == 2:
                        cpu_list += list(range(ends[0], ends[1] + 1))
                else:
                        cpu_list += [ends[0]]
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

# FIXME: move to python-linux-procfs
def is_hardirq_handler(self, pid):
                PF_HARDIRQ = 0x08000000
                try:
                        return int(self.processes[pid]["stat"]["flags"]) & \
                                PF_HARDIRQ and True or False
                except:
                        return False

def move_threads_to_cpu(cpus, pid_list, set_affinity_warning = None,
                        spread = False):
        changed = False

        ps = procfs.pidstats()
        cpu_idx = 0
        nr_cpus = len(cpus)
        new_affinity = cpus
        last_cpu = max(cpus) + 1
        for pid in pid_list:
                if spread:
                        new_affinity = [cpus[cpu_idx]]
                        cpu_idx += 1
                        if cpu_idx == nr_cpus:
                                cpu_idx = 0

                try:
                        try:
                                curr_affinity = schedutils.get_affinity(pid)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        continue
                                curr_affinity = None
                                raise e
                        if set(curr_affinity) != set(new_affinity):
                                try:
                                        schedutils.set_affinity(pid, new_affinity)
                                        curr_affinity = schedutils.get_affinity(pid)
                                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                        if e[0] == errno.ESRCH:
                                                continue
                                        curr_affinity == None
                                        raise e
                                if set(curr_affinity) == set(new_affinity):
                                        changed = True
                                        if is_hardirq_handler(ps, pid):
                                                try:
                                                        irq = int(ps[pid]["stat"]["comm"][4:])
                                                        bitmasklist = procfs.hexbitmask(new_affinity, last_cpu)
                                                        set_irq_affinity(irq, bitmasklist)
                                                except:
                                                        pass
                                elif set_affinity_warning:
                                        set_affinity_warning(pid, new_affinity)
                                else:
                                        print("move_threads_to_cpu: %s " % \
                                              (_("could not change %(pid)d affinity to %(new_affinity)s") % \
                                               {'pid':pid, 'new_affinity':new_affinity}))

                        # See if this is the thread group leader
                        if pid not in ps:
                                continue

                        threads = procfs.pidstats("/proc/%d/task" % pid)
                        for tid in list(threads.keys()):
                                try:
                                        curr_affinity = schedutils.get_affinity(tid)
                                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                        if e[0] == errno.ESRCH:
                                                continue
                                        raise e
                                if set(curr_affinity) != set(new_affinity):
                                        try:
                                                schedutils.set_affinity(tid, new_affinity)
                                                curr_affinity = schedutils.get_affinity(tid)
                                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                                if e[0] == errno.ESRCH:
                                                        continue
                                                raise e
                                        if set(curr_affinity) == set(new_affinity):
                                                changed = True
                                        elif set_affinity_warning:
                                                set_affinity_warning(tid, new_affinity)
                                        else:
                                                print("move_threads_to_cpu: %s " % \
                                                      (_("could not change %(pid)d affinity to %(new_affinity)s") % \
                                                       {'pid':pid, 'new_affinity':new_affinity}))
                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                        if e[0] == errno.ESRCH:
                                # process died
                                continue
                        elif e[0] == errno.EINVAL: # unmovable thread)
                                print("thread %(pid)d cannot be moved as requested" %{'pid':pid}, file=stderr)
                                continue
                        raise e
        return changed

def move_irqs_to_cpu(cpus, irq_list, spread = False):
        changed = 0
        unprocessed = []

        cpu_idx = 0
        nr_cpus = len(cpus)
        new_affinity = cpus
        last_cpu = max(cpus) + 1
        irqs = None
        ps = procfs.pidstats()
        for i in irq_list:
                try:
                        irq = int(i)
                except:
                        if not irqs:
                                irqs = procfs.interrupts()
                        irq = irqs.find_by_user(i)
                        if not irq:
                                unprocessed.append(i)
                                continue
                        try:
                                irq = int(irq)
                        except:
                                unprocessed.append(i)
                                continue

                if spread:
                        new_affinity = [cpus[cpu_idx]]
                        cpu_idx += 1
                        if cpu_idx == nr_cpus:
                                cpu_idx = 0

                bitmasklist = procfs.hexbitmask(new_affinity, last_cpu)
                set_irq_affinity(irq, bitmasklist)
                changed += 1
                pid = ps.find_by_name("IRQ-%d" % irq)
                if pid:
                        pid = int(pid[0])
                        try:
                                schedutils.set_affinity(pid, new_affinity)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        unprocessed.append(i)
                                        changed -= 1
                                        continue
                                raise e

        return (changed, unprocessed)

def affinity_remove_cpus(affinity, cpus, nr_cpus):
        # If the cpu being isolated was the only one in the current affinity
        affinity = list(set(affinity) - set(cpus))
        if not affinity:
                affinity = list(range(nr_cpus))
                affinity = list(set(affinity) - set(cpus))
        return affinity

# Shound be moved to python_linux_procfs.interrupts, shared with interrupts.parse_affinity, etc.
def parse_irq_affinity_filename(filename, nr_cpus):
        f = open("/proc/irq/%s" % filename)
        line = f.readline()
        f.close()
        return utilist.bitmasklist(line, nr_cpus)


def isolate_cpus(cpus, nr_cpus):
        fname = sys._getframe(  ).f_code.co_name # Function name
        ps = procfs.pidstats()
        ps.reload_threads()
        previous_pid_affinities = {}
        for pid in list(ps.keys()):
                if procfs.cannot_set_affinity(ps, pid):
                        continue
                try:
                        affinity = schedutils.get_affinity(pid)
                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                        if e[0] == errno.ESRCH:
                                continue
                        elif e[0] == errno.EINVAL:
                            print("Function:", fname, ",", e.strerror, file=sys.stderr)
                            sys.exit(2)
                        raise e
                if set(affinity).intersection(set(cpus)):
                        previous_pid_affinities[pid] = copy.copy(affinity)
                        affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
                        try:
                                schedutils.set_affinity(pid, affinity)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        continue
                                elif e[0] == errno.EINVAL:
                                    print("Function:", fname, ",", e.strerror, file=sys.stderr)
                                    sys.exit(2)
                                raise e

                if "threads" not in ps[pid]:
                        continue
                threads = ps[pid]["threads"]
                for tid in list(threads.keys()):
                        if procfs.cannot_set_thread_affinity(ps, pid, tid):
                                continue
                        try:
                                affinity = schedutils.get_affinity(tid)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        continue
                                elif e[0] == errno.EINVAL:
                                    print("Function:", fname, ",", e.strerror, file=sys.stderr)
                                    sys.exit(2)
                                raise e
                        if set(affinity).intersection(set(cpus)):
                                previous_pid_affinities[tid] = copy.copy(affinity)
                                affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
                                try:
                                        schedutils.set_affinity(tid, affinity)
                                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                        if e[0] == errno.ESRCH:
                                                continue
                                        elif e[0] == errno.EINVAL:
                                            print("Function:", fname, ",", e.strerror, file=sys.stderr)
                                            sys.exit(2)
                                        raise e

        del ps

        # Now isolate it from IRQs too
        irqs = procfs.interrupts()
        previous_irq_affinities = {}
        for irq in list(irqs.keys()):
                # LOC, NMI, TLB, etc
                if "affinity" not in irqs[irq]:
                        continue
                affinity = irqs[irq]["affinity"]
                if set(affinity).intersection(set(cpus)):
                        previous_irq_affinities[irq] = copy.copy(affinity)
                        affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
                        set_irq_affinity(int(irq),
                                         procfs.hexbitmask(affinity,
                                                           nr_cpus))

        affinity = parse_irq_affinity_filename("default_smp_affinity", nr_cpus)
        affinity = affinity_remove_cpus(affinity, cpus, nr_cpus)
        set_irq_affinity_filename("default_smp_affinity", procfs.hexbitmask(affinity, nr_cpus))

        return (previous_pid_affinities, previous_irq_affinities)

def include_cpus(cpus, nr_cpus):
        ps = procfs.pidstats()
        ps.reload_threads()
        previous_pid_affinities = {}
        for pid in list(ps.keys()):
                if procfs.cannot_set_affinity(ps, pid):
                        continue
                try:
                        affinity = schedutils.get_affinity(pid)
                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                        if e[0] == errno.ESRCH:
                                continue
                        raise e
                if set(affinity).intersection(set(cpus)) != set(cpus):
                        previous_pid_affinities[pid] = copy.copy(affinity)
                        affinity = list(set(affinity + cpus))
                        try:
                                schedutils.set_affinity(pid, affinity)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        continue
                                raise e

                if "threads" not in ps[pid]:
                        continue
                threads = ps[pid]["threads"]
                for tid in list(threads.keys()):
                        if procfs.cannot_set_thread_affinity(ps, pid, tid):
                                continue
                        try:
                                affinity = schedutils.get_affinity(tid)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        continue
                                raise e
                        if set(affinity).intersection(set(cpus)) != set(cpus):
                                previous_pid_affinities[tid] = copy.copy(affinity)
                                affinity = list(set(affinity + cpus))
                                try:
                                        schedutils.set_affinity(tid, affinity)
                                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                        if e[0] == errno.ESRCH:
                                                continue
                                        raise e

        del ps

        # Now include it in IRQs too
        irqs = procfs.interrupts()
        previous_irq_affinities = {}
        for irq in list(irqs.keys()):
                # LOC, NMI, TLB, etc
                if "affinity" not in irqs[irq]:
                        continue
                affinity = irqs[irq]["affinity"]
                if set(affinity).intersection(set(cpus)) != set(cpus):
                        previous_irq_affinities[irq] = copy.copy(affinity)
                        affinity = list(set(affinity + cpus))
                        set_irq_affinity(int(irq),
                                         procfs.hexbitmask(affinity, nr_cpus))

        affinity = parse_irq_affinity_filename("default_smp_affinity", nr_cpus)
        affinity = list(set(affinity + cpus))
        set_irq_affinity_filename("default_smp_affinity", procfs.hexbitmask(affinity, nr_cpus))

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

def get_policy_and_rtprio(parm):
        parms = parm.split(":")
        rtprio = 0
        policy = None
        if parms[0].upper() in ["OTHER", "BATCH", "IDLE", "FIFO", "RR"]:
                policy = schedutils.schedfromstr("SCHED_%s" % parms[0].upper())
                if len(parms) > 1:
                        rtprio = int(parms[1])
                elif parms[0].upper() in ["FIFO", "RR"]:
                        rtprio = 1
        elif parms[0].isdigit():
                rtprio = int(parms[0])
        else:
                raise ValueError
        return (policy, rtprio)

def thread_filtered(tid, cpus_filtered, show_kthreads, show_uthreads):
        if cpus_filtered:
                try:
                        affinity = schedutils.get_affinity(tid)
                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                        if e[0] == errno.ESRCH:
                                return False
                        raise e

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
        try:
                (policy, rtprio) = get_policy_and_rtprio(parm)
        except ValueError:
                print("tuna: " + _("\"%s\" is unsupported priority value!") % parms[0])
                return

        for tid in tids:
                try:
                        thread_set_priority(tid, policy, rtprio)
                except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                        if e[0] == errno.ESRCH:
                                continue
                        raise e
                if affect_children:
                        for child in [int (a) for a in os.listdir("/proc/%d/task" % tid)]:
                                if child != tid:
                                        try:
                                                thread_set_priority(child, policy, rtprio)
                                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                                if e[0] == errno.ESRCH:
                                                        continue
                                                raise e

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
        for pid in list(proc.keys()):
                name = proc[pid]["stat"]["comm"]
                # Trying to set the priority of the migration threads will
                # fail, at least on 3.6.0-rc1 and doesn't make sense anyway
                # and this function is only used to save those priorities
                # to reset them using tools like rtctl, skip those to
                # avoid sched_setscheduler/chrt to fail
                if iskthread(pid) and not name.startswith("migration/"):
                        rtprio = int(proc[pid]["stat"]["rt_priority"])
                        try:
                                policy = schedutils.get_scheduler(pid)
                                affinity = schedutils.get_affinity(pid)
                        except (SystemError, OSError) as e: # old python-schedutils incorrectly raised SystemError
                                if e[0] == errno.ESRCH:
                                        continue
                                raise e
                        percpu = iskthread(pid) and \
                                 proc.is_bound_to_cpu(pid)
                        kthreads[name] = sched_tunings(name, pid, policy,
                                                       rtprio, affinity,
                                                       percpu)

        return kthreads

def run_command(cmd, policy, rtprio, cpu_list):
        newpid = os.fork()
        if newpid == 0:
                cmd_list = shlex.split(cmd)
                pid = os.getpid()
                if rtprio:
                        try:
                                thread_set_priority(pid, policy, rtprio)
                        except (SystemError, OSError) as err:
                                print("tuna: %s" % err)
                                sys.exit(2)
                if cpu_list:
                        try:
                                schedutils.set_affinity(pid, cpu_list)
                        except (SystemError, OSError) as err:
                                print("tuna: %s" % err)
                                sys.exit(2)

                try:
                        os.execvp(cmd_list[0], cmd_list)
                except (SystemError, OSError) as err:
                        print("tuna: %s" % err)
                        sys.exit(2)
        else:
                os.waitpid(newpid, 0);

def generate_rtgroups(filename, kthreads, nr_cpus):
        f = open(filename, "w")
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
        names = list(kthreads.keys())
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
                if kt.percpu or idx != 0 or name == "posix_cpu_timer":
                        # Don't mess with workqueues, etc
                        # posix_cpu_timer is too long and doesn't
                        # have PF_THREAD_BOUND in its per process
                        # flags...
                        mask = "*"
                else:
                        mask = ",".join([hex(a) for a in \
                                         procfs.hexbitmask(kt.affinity, nr_cpus)])
                f.write("%s:%c:%d:%s:\[%s\]$\n" % (name,
                                                   schedutils.schedstr(kt.policy)[6].lower(),
                                                   kt.rtprio, mask, regex))
        f.close()


def nohz_full_list():
        return [ int(cpu) for cpu in procfs.cmdline().options["nohz_full"].split(",") ]
