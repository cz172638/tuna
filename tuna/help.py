
import gettext
_ = gettext.gettext

# gettext_noop
def N_(s):
        return s

KTHREAD_HELP = {
'kthreadd':N_('Used to create kernel threads via kthread_create(). It is the parent of all the other kernel threads.'),
'posix_cpu_timer':N_('Per-cpu thread that handles POSIX timer callbacks. Timer callbacks are bound to a cpu and are handled by these threads as per-cpu data.'),
'kondemand/':N_('This cpufreq workqueue runs periodically to sample the idleness of the system, increasing or reducing the CPU frequency to save power. \n[One per CPU]'),
'sirq-rcu/':N_('Pushes the RCU grace period along (if possible) and will handle dereferenced RCU callbacks, such as freeing structures after a grace period. \n[One per CPU]'),
'khelper':N_('Used to call user mode helpers from the kernel, such as /sbin/bridge-stp, ocfs2_hb_ctl, pnpbios, poweroff, request-key, etc."'),
'group_balance':N_('Scheduler load balance monitoring.'),
'kjournald':N_('Main thread function used to manage a filesystem logging device journal. This kernel thread is responsible for two things: <b>COMMIT</b>: Every so often we need to commit the current state of the filesystem to disk.  The journal thread is responsible for writing all of the metadata buffers to disk. <b>CHECKPOINT</b>: We cannot reuse a used section of the log file until all of the data in that part of the log has been rewritten elsewhere on the disk.  Flushing these old buffers to reclaim space in the log is known as checkpointing, and this thread is responsible for that job.'),
'lockd':N_('Locking arbiter for NFS on the system'),
'sirq-sched/':N_('Triggered when a rebalance of tasks is needed to CPU domains. This handles balancing of SCHED_OTHER tasks across CPUs. RT tasks balancing is done directly in schedule and wakeup paths.  Runs at prio 1 because it needs to schedule above all SCHED_OTHER tasks. If the user has the same issue but doesn"t mind having latencies against other kernel threads that run here, then its fine. But it should definitely be documented that PRIO 1 has other threads on it at boot up. \n[One per CPU]'),
'sirq-high/':N_('This is from a poor attempt to prioritize tasklets. Some tasklets wanted to run before anything else. Thus there were two tasklet softirqs made. tasklet_vec and tasklet_hi_vec. A driver writer could put their "critical" tasklets into the tasklet_hi_vec and it would run before other softirqs. This never really worked as intended. \n[One per CPU]'),
'kblockd/':N_('Workqueue used to process IO requests. Used by IO schedulers and block device drivers. \n[One per CPU]'),
'sirq-net-rx/':N_('When receiving a packet the device will place the packet on a queue with its hard interrupt (threaded in RT). The sirq-net-rx is responsible for finding out what to do with the packet. It may forward it to another box if the current box is used as a router, or it will find the task the packet is for. If that task is currently waiting for the packet, the softirq might hand it off to that task and the task will handle the rest of the processing of the packet. \n[One per CPU]'),
'krcupreemptd':N_('This should run at the lowest RT priority. With preemptible RCU, a loaded system may have tasks that hold RCU locks but have a high nice value. These tasks may be pushed off for seconds, and if the system is tight on memory, the RCU deferred freeing may not occur. The result can be drastic.  The krcupreemptd is a daemon that runs just above SCHED_OTHER and wakes up once a second and performs a synchronize RCU. With RCU boosting, all those that hold RCU locks will inherit the priority of the krcupreemptd and wake up and release the RCU locks.  This is only a concern for loaded systems and SCHED_OTHER tasks. If there is an issue of RT tasks starving out SCHED_OTHER tasks and causing problems with freeing memory, then the RT tasks are designed badly.'),
'ksoftirqd/':N_('Activated when under heavy networking activity. Used to avoid monopolizing the CPUs doing just software interrupt processing. \n[One per CPU]'),
'sirq-timer/':N_('Basically the timer wheel. Things that add itself to the timer wheel timeouts will be handled by this softirq. Parts of the kernel that need timeouts will use this softirq (i.e. network timeouts). The resolution to these timeouts are defined by the HZ value. \n[One per CPU]'),
'events/':N_('Global workqueue, used to schedule work to be done in process context. \n[One per CPU]'),
'watchdog/':N_('Run briefly once per second to reset the softlockup timestamp.  If this gets delayed for more than 60 seconds then a message will be printed.  Use /proc/sys/kernel/hung_task_timeout_secs and /proc/sys/kernel/hung_task_check_count to control this behaviour.  Setting /proc/sys/kernel/hung_task_timeout_secs to zero will disable this check. \n[One per CPU]'),
'sirq-net-tx/':N_('This is the network transmit queue. Most of the time the network packets will be handled by the task that is sending the packets out, and doing so at the priority of that task. But if the protocol window or the network device queue is full, then the packets will be pushed off to later. The sirq-net-tx softirq is responsible for sending out these packets. \n[One per CPU]'),
'sirq-block/':N_('Called after a completion to a block device is made. Looking further into this call, I only see a couple of users. The SCSI driver uses this as well as cciss. \n[One per CPU]'),
'sirq-tasklet/':N_('Catch all for those devices that couldn"t use softirqs directly and mostly made before work queues were around. The difference between a tasklet and a softirq is that the same tasklet can not run on two different CPUs at the same time. In this regard it acts like a "task" (hence the name "tasklet"). Various devices use tasklets. \n[One per CPU]'),
'usb-storage':N_('Per USB storage device virtual SCSI controller.  Persistant across device insertion/removal, as is the SCSI node. This is done so that a device which is removed can be re-attached and be granted the same /dev node as before, creating persistance between connections of the target unit.  Gets commands from the SCSI mid-layer and, after sanity checking several things, sends the command to the "protocol" handler. This handler is responsible for re-writing the command (if necessary) into a form which the device will accept. For example, ATAPI devices do not support 6-byte commands. Thus, they must be re-written into 10-byte variants.'),
'migration/':N_('High priority system thread that performs thread migration by bumping thread off CPU then pushing onto another runqueue. \n[One per CPU]'),
'rpciod/':N_('Handles Sun RPC network messages (mainly for NFS) \n[One per CPU]')
}

