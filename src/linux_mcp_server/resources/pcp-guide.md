# Performance Co-Pilot (PCP) metrics guide

Performance Co-Pilot records system metrics continuously and stores them in archives,
so you can see what a system was doing hours or days ago, not just now.

Metric names are exact strings. A plausible-looking but wrong name returns an error or
no data, so take names from the catalog below rather than recalling them from memory.

## Choosing a tool

1. `get_system_information` — reports whether PCP is installed and running, and what
   time ranges its archives cover. Check the range before asking for a time outside it.
2. `pcp_performance_summary` — one broad snapshot (CPU, memory, disk, network, top
   processes), live or at a single moment in the past. Start here when you do not yet
   know which subsystem is at fault.
3. `pcp_query_metrics` — a time series of specific metrics. Use it once you know what
   to look at.
4. `pcp_list_metrics` — browse the metric namespace for something this guide does not
   cover. It lists one level at a time, so start broad and drill in, and it lists only
   what this system records, so everything in it can be queried.

## Time arguments

`start_time` and `end_time` accept an absolute timestamp (`2026-08-14 14:00:00`) or an
offset (`-2hours`, `-30min`, `now`). A time given without a UTC offset is read in the
**target system's** timezone, and results come back in that timezone.

Pass `start_time`, `end_time` and `interval` together for an exact window. If you omit
`interval`, one is chosen to give roughly 20 samples across the range, which is usually
what you want. Omitting both times gives the last hour.

A long range at a short interval produces a lot of output. Use a coarse interval first
to find when something happened, then re-query that narrower window finely.

## Reading the results

`pcp_query_metrics` returns JSON samples:

```json
[{"time": "2026-08-14T14:00:00+10:00", "metrics": {"<column>": "<value>"}}]
```

**Per-instance columns.** Many metrics carry one value per CPU, disk, interface or
filesystem. Each instance becomes its own column, named `metric-instance`:

```
disk.dev.read_bytes-sda            disk.dev.read_bytes-nvme0n1
network.interface.in.bytes-eth0    filesys.full-/dev/mapper/rhel-root
kernel.all.load-1 minute           kernel.all.load-5 minute
```

The catalog marks these `[per-X]`. Unmarked metrics have a single value.

**Counters are already rate-converted.** Metrics marked `[counter]` are cumulative
since boot, but are reported to you as a **per-second rate**. `disk.dev.read_bytes` is
Kbytes read per second during that sample, not Kbytes read since boot. Catalog entries
for counters therefore say what is counted, not "per second". Do not subtract
consecutive samples — that would give you the rate of a rate.

Anything not marked `[counter]` is an instantaneous reading, reported as-is.

**Prefer the ready-made percentages.** Where both exist, use the derived metric instead
of doing arithmetic on raw counters: the kernel.cpu.util metrics rather than the
kernel.all.cpu ones, and `disk.dev.util` and `disk.dev.await` rather than
`disk.dev.avactive` and `disk.dev.read_rawactive`.

**Units are not implied by the name.** A `_bytes` metric is not necessarily in bytes:
`disk.dev.read_bytes` and the mem.util metrics are in **Kbytes**, while
`network.interface.in.bytes` and `swap.used` really are in bytes. The catalog gives the
unit wherever it is not obvious; use it rather than assuming.

**Missing values.** A metric with no value at a given sample is omitted from that sample
rather than reported as null. A column absent from every sample usually means the
metric is not recorded on this system.

## Metric catalog

These are recorded by a default `pmlogger` configuration on a recent RHEL system, so
they are normally available for historical queries.

### CPU utilization

Prefer these. They are percentages across all CPUs and need no conversion.

- `kernel.cpu.util.user` — percentage of user time, including guest
- `kernel.cpu.util.sys` — percentage of system time
- `kernel.cpu.util.idle` — percentage of idle time
- `kernel.cpu.util.wait` — percentage of time blocked on I/O
- `kernel.cpu.util.steal` — percentage taken by the hypervisor; high values mean the
  host is oversubscribed
- `kernel.cpu.util.nice` — percentage of nice user time
- `kernel.cpu.util.intr` — percentage of interrupt time

Raw CPU time counters, for per-CPU detail or a breakdown the above lacks. These count
CPU time in **milliseconds**, so as rates they read as milliseconds of CPU time per
second: 1000 is one logical CPU fully occupied, and the ceiling across the system is
1000 × `hinv.ncpu`.

- `kernel.all.cpu.user`, `kernel.all.cpu.sys`, `kernel.all.cpu.idle`,
  `kernel.all.cpu.nice`, `kernel.all.cpu.steal`, `kernel.all.cpu.guest` `[counter]`
- `kernel.all.cpu.wait.total` — time blocked on I/O `[counter]`
- `kernel.all.cpu.irq.hard`, `kernel.all.cpu.irq.soft` — interrupt time `[counter]`
- `kernel.percpu.cpu.user`, `kernel.percpu.cpu.sys`, `kernel.percpu.cpu.idle`,
  `kernel.percpu.cpu.wait.total`, `kernel.percpu.cpu.steal` — per logical CPU
  `[counter]` `[per-CPU]`
- `kernel.pernode.cpu.user`, `kernel.pernode.cpu.sys`, `kernel.pernode.cpu.idle`,
  `kernel.pernode.cpu.steal` — per NUMA node `[counter]` `[per-node]`

### Load and scheduling

- `kernel.all.load` — load average `[per-interval: 1 minute, 5 minute,
  15 minute]`
- `kernel.all.runnable` — processes on a run queue; compare against `hinv.ncpu`
- `kernel.all.running` — processes currently running
- `kernel.all.blocked` — processes in uninterruptible sleep, usually waiting on I/O
- `kernel.all.nprocs` — total processes and threads
- `kernel.all.pswitch` — context switches `[counter]`
- `kernel.all.intr` — interrupts `[counter]`
- `kernel.all.sysfork` — forks `[counter]`
- `kernel.all.uptime` — seconds since boot; a drop means the system rebooted

### Pressure stall information (PSI)

The clearest signal that a resource is actually hurting the workload. `some` means at
least one task was delayed; `full` means nothing could make progress.

- `kernel.all.pressure.cpu.some.avg` — percentage of time tasks were delayed waiting
  for CPU `[per-window: 10 second, 1 minute, 5 minute]`
- `kernel.all.pressure.memory.some.avg` — delayed on memory `[per-window]`
- `kernel.all.pressure.memory.full.avg` — all work stalled on memory
  `[per-window]`
- `kernel.all.pressure.io.some.avg` — delayed on I/O `[per-window]`
- `kernel.all.pressure.io.full.avg` — all work stalled on I/O `[per-window]`

### Memory

All in Kbytes unless noted.

- `mem.physmem` — total usable physical memory
- `mem.util.available` — memory available for new work without swapping; **this is the
  one to watch**, not `mem.util.free`
- `mem.util.used` — used memory; counts page cache as used
- `mem.util.free` — genuinely unallocated memory; low is normal and not a problem on
  its own
- `mem.util.cached` — page cache
- `mem.util.bufmem` — I/O buffers
- `mem.util.anonpages` — anonymous pages, i.e. real process memory
- `mem.util.slab` — kernel slab allocations
- `mem.util.dirty` — dirty pages awaiting writeback
- `mem.util.shmem` — shared memory and tmpfs
- `mem.util.committed_AS` — memory committed to address spaces
- `mem.util.commitLimit` — commit ceiling; compare with `mem.util.committed_AS`

Memory pressure and reclaim:

- `mem.vmstat.pgmajfault` — major faults, i.e. faults served from disk; the key sign
  of thrashing `[counter]`
- `mem.vmstat.pgfault` — all page faults `[counter]`
- `mem.vmstat.pgscan_direct_total` — pages scanned by direct reclaim; nonzero means
  allocation is stalling `[counter]`
- `mem.vmstat.pgscan_kswapd_total` — pages scanned by kswapd `[counter]`
- `mem.vmstat.pgsteal_total` — pages reclaimed `[counter]`
- `mem.vmstat.oom_kill` — OOM kills `[counter]`
- `mem.vmstat.pswpin` — pages swapped in `[counter]`
- `mem.vmstat.pswpout` — pages swapped out `[counter]`

### Swap

- `swap.length` — total swap configured, bytes
- `swap.used` — swap in use, bytes; a high but static value is usually harmless
- `swap.free` — swap free, bytes
- `swap.pagesin` — pages read from swap `[counter]`
- `swap.pagesout` — pages written to swap; sustained traffic here is the real sign of
  swap trouble `[counter]`

### Disk I/O

Per-device metrics are instanced by device name (`sda`, `nvme0n1`). Use the disk.dm
metrics for LVM and device-mapper volumes, and `hinv.map.dmname` to map `dm-N` to a
friendly name.

- `disk.dev.util` — percentage of time the device was busy `[per-device]`
- `disk.dev.await` — average time a request spent queued and serviced, milliseconds
  `[per-device]`
- `disk.dev.r_await` — the same for reads `[per-device]`
- `disk.dev.w_await` — the same for writes `[per-device]`
- `disk.dev.read`, `disk.dev.write`, `disk.dev.total` — operations `[counter]`
  `[per-device]`
- `disk.dev.read_bytes`, `disk.dev.write_bytes`, `disk.dev.total_bytes` — **Kbytes**,
  not bytes `[counter]` `[per-device]`
- `disk.dev.aveq` — time-averaged request queue length `[counter]` `[per-device]`
- `disk.all.read`, `disk.all.write`, `disk.all.total` — operations summed over all
  disks `[counter]`
- `disk.all.read_bytes`, `disk.all.write_bytes`, `disk.all.total_bytes` — **Kbytes**
  summed over all disks `[counter]`
- `disk.dm.util` — percentage busy, per device-mapper volume `[per-dm-device]`
- `disk.dm.await` — average request time in milliseconds, per device-mapper volume
  `[per-dm-device]`
- `disk.dm.read_bytes`, `disk.dm.write_bytes` — Kbytes, per device-mapper volume
  `[counter]` `[per-dm-device]`

### Filesystems

Instanced by device; `filesys.mountdir` gives the mount point for each.

- `filesys.full` — percentage of the filesystem in use; the quickest check
  `[per-filesystem]`
- `filesys.capacity`, `filesys.used`, `filesys.free` — Kbytes
  `[per-filesystem]`
- `filesys.avail` — Kbytes free to non-root; what ordinary processes can actually use
  `[per-filesystem]`
- `filesys.maxfiles`, `filesys.usedfiles`, `filesys.freefiles` — inode counts; a
  filesystem can run out of inodes while still having free space
  `[per-filesystem]`
- `filesys.mountdir` — mount point `[per-filesystem]`
- `filesys.type` — filesystem type `[per-filesystem]`

### Network

Instanced by interface name.

- `network.interface.in.bytes`, `network.interface.out.bytes` — bytes, not Kbytes
  `[counter]` `[per-interface]`
- `network.interface.in.packets`, `network.interface.out.packets` — packets
  `[counter]` `[per-interface]`
- `network.interface.in.errors`, `network.interface.out.errors` — errors; should be
  zero `[counter]` `[per-interface]`
- `network.interface.in.drops`, `network.interface.out.drops` — dropped packets
  `[counter]` `[per-interface]`
- `network.interface.speed` — link speed in Mbytes per second; use it to turn byte
  rates into link utilization `[per-interface]`
- `network.interface.up` — whether the link is up `[per-interface]`

TCP and UDP, system-wide:

- `network.tcp.retranssegs` — segments retransmitted; compare against
  `network.tcp.outsegs` for a loss rate `[counter]`
- `network.tcp.insegs`, `network.tcp.outsegs` — segments `[counter]`
- `network.tcp.activeopens` — outgoing connections established `[counter]`
- `network.tcp.passiveopens` — incoming connections accepted `[counter]`
- `network.tcp.attemptfails` — failed connection attempts `[counter]`
- `network.tcp.listendrops` — SYNs dropped because the accept queue was full, i.e. a
  backlogged server `[counter]`
- `network.tcp.listenoverflows` — listen queue overflows `[counter]`
- `network.udp.indatagrams`, `network.udp.outdatagrams` — datagrams `[counter]`
- `network.udp.inerrors` — UDP receive errors `[counter]`
- `network.sockstat.tcp.inuse` — TCP sockets in use
- `network.sockstat.tcp.tw` — sockets in TIME_WAIT
- `network.sockstat.tcp.orphan` — orphaned sockets
- `network.sockstat.total` — all sockets in use

### Processes

- `proc.nprocs` — number of processes
- `proc.runq.runnable` — processes on a run queue
- `proc.runq.blocked` — processes in uninterruptible sleep
- `vfs.files.count`, `vfs.files.max` — open file handles against the system limit
- `vfs.inodes.count`, `vfs.dentry.count` — in-use inode and dentry structures

Per-process history is thin. Archives keep only these three, instanced once per
process, and **each produces one column per process, so a busy system yields hundreds
of columns.** Query them over a short window with a coarse interval, and only after the
system-wide metrics have told you which resource is under strain.

- `proc.memory.rss` — resident set size, Kbytes `[per-process]`
- `proc.memory.size` — virtual size, Kbytes `[per-process]`
- `proc.psinfo.maj_flt` — major faults `[counter]` `[per-process]`

There is no archived per-process CPU time, so historical questions of the form "which
process was burning the CPU" cannot be answered from metrics alone. Use
`pcp_performance_summary` at the time of interest instead; it reports top processes.

### System inventory

Constant or slow-changing values.

- `hinv.ncpu` — number of logical CPUs; divide `kernel.all.runnable` by this
- `hinv.physmem` — total physical memory, Mbytes
- `hinv.ndisk`, `hinv.nfilesys`, `hinv.ninterface` — device counts
- `hinv.nnode` — NUMA nodes
- `hinv.pagesize` — page size in bytes
- `hinv.machine` — hardware architecture
- `hinv.cpu.model_name` — CPU model `[per-CPU]`
- `hinv.map.dmname` — maps `dm-N` to its persistent name, for reading the disk.dm
  instances `[per-dm-device]`
- `kernel.uname.release` — kernel release recorded in the archive
- `kernel.uname.distro` — distribution name
- `kernel.uname.nodename` — hostname

## If a metric you need is not listed

Anything outside this catalog — XFS internals, NFS, KVM, IPC, per-CPU interrupts,
SCSI or fibre channel — may still be reachable through `pcp_list_metrics`. Call it
with no prefix for the top-level namespaces, then again with the one you want in
order to see inside it. Narrow the problem down with the metrics above first, so
that you know which subsystem to browse.

Which metrics are recorded depends on how the system is configured, so some of the
ones above may be missing here; `pcp_query_metrics` returns an error for those.
`pcp_list_metrics` lists specifically what this system's `pmlogger` records and
`pcp_query_metrics` can return. When a metric is not there, fall back to the closest
one that is rather than retrying variations on the name.
