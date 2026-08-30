# kernel-deltas

Tracks what moves in the iOS kernel between builds. When Apple ships a new
signed iOS build for the boards below, this repo pulls just the kernel out
of the IPSW (about 20 MB out of an 8.45 GB download), resolves every offset
with XPF, diffs it against the previous build, and commits a report. No
device, no jailbreak, no full IPSW.

[![kcwatch workflow](https://github.com/kaffeindecaf/kernel-deltas/actions/workflows/watch.yml/badge.svg)](https://github.com/kaffeindecaf/kernel-deltas/actions)

Watching t8030 (A13, iPhone SE 2) and t8110 (A15, iPhone 14) since 2026-08-25.

| where | what |
|---|---|
| [kernel-deltas.md](kernel-deltas.md) | the feed, readable inline on GitHub |
| [atom.xml](atom.xml) | subscribe in any RSS reader |
| [`reports/`](reports/) | one markdown report per release pair |

## What is an offset

The kernel is full of structs (proc, task, vm_map, ...). Exploit code reads
and writes kernel memory through those structs, and it has to know "field X
sits N bytes into struct Y". That N is the offset. Apple shuffles struct
layout between major iOS versions, so kernel exploits ship with a table of
offsets per iOS version (kexploit/offsets.m here, shared with W0lfSword).

This repo answers one question on every new build: did any of those offsets
move? A YES verdict means the existing offset table still applies to the new
build. A NO verdict means struct layout changed and the table needs a new
version block before kernel work will work.

## Status

| board | SoC | device | last build | report |
|---|---|---|---|---|
| t8030 | A13 | iPhone SE 2 | 26.6.1 (23G83) | [reports/t8030-26.6.1-23G83.md](reports/t8030-26.6.1-23G83.md) |
| t8110 | A15 | iPhone 14 | 26.6.1 (23G83) | [reports/t8110-26.6.1-23G83.md](reports/t8110-26.6.1-23G83.md) |

Baseline (2026-08-25): 26.6 (23G71) -> 26.6.1 (23G83), xnu
12377.162.13~2 -> 12377.162.14~4, on both boards. t8030: 53 identical, 12
symbol addresses shifted, 0 struct moves. t8110: 53 identical, 13 shifted,
0 struct moves. task.itk_space 0x310 and proc.struct_size 0x750 verified on
both.

The resolved set covers 65-66 offsets per build: base/translation globals,
physmap, proc/task/vm_map struct fields, trust cache, sandbox counts, plus
the extended symbols (pmap_bootstrap, phystokv, arm_vm_init, fatal_error_fmt,
iorvbar, task_collect_crash_info, proc_get_syscall_filter_mask_size, ...).
proc.p_name resolves per board (t8030 0x470, t8110 0x488; see `kcwatch
verify`: W0lfSword's offsets.m 26.x block still lists 0x57d).

## Reading a report

Real 26.6 -> 26.6.1 report (t8030):

```
xnu: 12377.162.13~2 -> 12377.162.14~4
resolved: A=65  B=65   identical: 53   changed: 12   degraded: 0

CHANGED:
  kernelSymbol.vn_kqfilter: 0xfffffff009ee6730 -> 0xfffffff009ee6974
  kernelSymbol.pmap_enter_options_addr: 0xfffffff009e6ab20 -> 0xfffffff009e6ad64
  ...

VERDICT: YES: offsets.m block '>= 26.0' applies to 26.6.1 (all struct/constant
offsets identical to previous build)
```

The last line is the one that matters. YES = the existing offset table still
works on the new build. NO = struct layout moved, the table needs a new
version block.

What each signal means:

| signal | meaning |
|---|---|
| struct offset moved | kernel struct layout changed, offsets table needs a new block |
| symbol address shifted | code around that symbol changed, check Apple advisories |
| syscall count changed | syscalls added/removed, new attack surface |
| item went UNRESOLVED | a field or function vanished, investigate |
| kernel base / entry moved | KASLR layout change, relevant for exploit geometry |

## How it works

```
ipsw.me ---- poll for new signed build
                 |
                 v
        fetch kernelcache only   (HTTP Range, ~20 MB of 8.45 GB, CRC-verified)
                 |
                 v
        resolve with XPF         (host-side patchfinder, IMG4 + filesets)
                 |
                 v
        diff vs previous build   (struct offsets / constants / symbols)
                 |
                 v
        report + feed + atom     (committed automatically)
```

The pipeline is scripts/kcwatch.py and runs daily at 06:00 UTC via GitHub
Actions (.github/workflows/watch.yml). It is built on the W0lfSword iOS
toolkit and shares its offset tables, so a NO verdict here is a direct
signal for anyone maintaining exploit offsets.

## Run it yourself

The pipeline ships in W0lfSword:

```bash
git clone https://github.com/kaffeindecaf/W0lfSword
cd W0lfSword
./W0lfSword kcwatch poll --board t8030     # check for a new build
./W0lfSword kcwatch verify --board t8030   # offsets.m vs live kernelcache
```

Or drive this repo directly:

```bash
python3 scripts/kcwatch.py poll --board t8030   # fetch -> resolve -> diff -> report
python3 scripts/kcwatch.py verify --board t8030 # is the offsets table still valid?
python3 scripts/kcwatch.py index                # render kernel-deltas.md
python3 scripts/kcwatch.py atom                 # render atom.xml
```

Needs the prebuilt tools/xpf-cli binary and liblzfse1.

## Adding offsets

The feed only diffs what the xpf-cli binary resolves. That list lives in
tools/xpf-cli/xpf_patched.c, grouped into sets (base, translation, physmap,
struct, extended, sandbox, ...). Each entry is a metric name like
`kernelSymbol.pmap_bootstrap` or `kernelStruct.task.itk_space`. The finder
for each name lives in the XPF source (XPF/src/common.c, non_ppl.c, ppl.c,
bad_recovery.c), which is not vendored here - only the prebuilt binary is.

Steps:

1. Check the name exists. Finders are registered with xpf_item_register()
   in the xpf_*_init() functions. A name with no registered finder prints
   0x0 silently, so grep the XPF source for the name first.
2. Add the metric string to the right set in xpf_patched.c. If the finder
   does not exist yet, write one (PFPatternMetric pattern scan or an xref
   walk, same style as the neighbours) and register it in init.
3. Rebuild. build.sh compiles XPF/src + ChOma, so run it in a W0lfSword
   checkout (which has XPF/), then copy the fresh binary and xpf_patched.c
   back into tools/xpf-cli/.
4. Re-resolve the cached kernelcaches:

   ```bash
   tools/xpf-cli/xpf-cli .kcwatch/t8030/26.6.1-23G83.img4 > state/t8030/26.6.1-23G83.txt
   ```

   Do that for every board and build you want in the feed. The kernelcache
   IMG4s are gitignored, so on a fresh clone re-fetch one with
   `kcwatch poll --version <ver>` first. The dump format is one line per
   item: `0x0000000000000310 <- kernelStruct.task.itk_space`.
5. Rebuild the feed artifacts:

   ```bash
   python3 scripts/regenerate_dumps.py        # reports + state from the new dumps
   python3 scripts/kcwatch.py index           # kernel-deltas.md
   python3 scripts/kcwatch.py atom            # atom.xml
   ```

6. Commit the new dumps, reports, feed, and the rebuilt binary.

Optional: make `kcwatch verify` check the new offset against
kexploit/offsets.m. Verify maps dump item `kernelStruct.<x>.<y>` to variable
`off_<x>_<y>`, so a struct offset named kernelStruct.task.map needs
`off_task_map = 0x...` in the right version block of offsets.m (which is
vendored from W0lfSword; re-sync with
`cp <W0lfSword>/kexploit/offsets.m kexploit/offsets.m`). Symbol addresses do
not need offsets.m entries.

Adding a board is a separate change: one line in the BOARDS dict in
scripts/kcwatch.py (t8103, A14, is already defined) plus a loop entry in
.github/workflows/watch.yml.

## Repo layout

```
kernel-deltas.md      the feed index (regenerated each run)
atom.xml              RSS/Atom feed
reports/              one markdown report per release pair
state/<board>/        raw XPF dumps + watcher state (the evidence)
scripts/              kcwatch.py (orchestrator) - kczip.py (ranged fetch) - xpf_diff.py
tools/xpf-cli/        the prebuilt patchfinder (source + shims + binary)
kexploit/offsets.m    the vendored offset table the verdict compares against
.github/workflows/    the daily cron
```

## FAQ

**Does this run on a device?** No. Everything is host-side against Apple's
CDN, that is the whole point.

**"Identical" means safe, right?** No. Identical offsets = same layout,
nothing more. It says nothing about exploitability.

**Why per-board?** Offsets can differ per SoC within the same build. Every
report states its board; a t8030 result does not transfer to another SoC
without checking.

**What is "degraded"?** An item that went from resolved to unresolved
between builds. Usually means the structure changed; sometimes it is a PPL
item that never resolves (expected in every build).

**A new iOS dropped and there is no report yet?** The cron runs daily at
06:00 UTC. Check the [workflow runs](https://github.com/kaffeindecaf/kernel-deltas/actions).

**Can I add offsets?** Yes, see "Adding offsets" above.

## Glossary

| term | plain meaning |
|---|---|
| kernelcache | the compressed kernel plus its data, inside every IPSW |
| offset | "where in the struct is field X" - the number exploit code adds to a struct pointer |
| offset table | the per-iOS list of those numbers (offsets.m in W0lfSword) |
| XPF | a host-side patchfinder: finds offsets by scanning the kernel image, no device needed |
| IMG4 | the signed container format the kernelcache ships in |
| fileset | modern iOS splits the kernel into pieces; filesets are the pieces |
| SPTM | the SoC's "secure page table monitor" - a chunk of the kernel lives behind it |
| t8030 / t8110 | Apple SoC codenames: A13 / A15 |
| xnu | the kernel itself (its version string is per-build) |

## Caveats

- Reports describe layout, not vulnerability. Same offsets != exploitable.
- Apple advisories land after releases. This feed is the "before" half.
- A handful of PPL items read UNRESOLVED in every build, expected, not a
  regression.

## Credits

- XPF patchfinder + pipeline: [W0lfSword](https://github.com/kaffeindecaf/W0lfSword)
  (tools/xpf-cli)
- Ranged-fetch technique proven against real Apple CDN IPSWs during the K4.1
  offset verification
- Release metadata: [ipsw.me](https://ipsw.me) API
