# 🐺 kernel-deltas

**What changed in the iOS kernel between builds — automatically.**

[![kcwatch workflow](https://github.com/kaffeindecaf/kernel-deltas/actions/workflows/watch.yml/badge.svg)](https://github.com/kaffeindecaf/kernel-deltas/actions)
[![feed](https://img.shields.io/badge/feed-markdown-3fb950)](kernel-deltas.md)
[![atom/rss](https://img.shields.io/badge/atom-rss-d29922)](atom.xml)

Every time Apple ships a new signed iOS build, this repo fetches just the
kernel out of the IPSW, resolves every offset, diffs it against the previous
build, and publishes a report — within hours, with **no devices, no
jailbreaks, no 8 GB downloads**.

Watching **t8030** (A13 · iPhone SE 2) and **t8110** (A15 · iPhone 14) since
2026-08-25.

| where | what |
|---|---|
| 📄 [kernel-deltas.md](kernel-deltas.md) | the feed, readable inline on GitHub |
| 📡 [atom.xml](atom.xml) | subscribe in any RSS reader |
| 📰 [`reports/`](reports/) | one markdown report per release pair |

---

## TL;DR

1. Apple ships iOS **26.6.1**.
2. This repo grabs the kernelcache (≈20 MB of an 8.45 GB IPSW) and resolves
   the offset table with XPF.
3. It diffs against the previous build and answers one question:
   **did anything move?**
4. You read the verdict in a report — or in your RSS reader.

---

## What you get

A short example — the real 26.6 → 26.6.1 report:

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

The last line is the one that matters: **YES** = your existing offset table
still works on the new build. **NO** = struct layout moved, the table needs a
new version block before anything kernel-related will work.

What each signal in a report means:

| signal | meaning |
|---|---|
| struct offset moved | kernel struct layout changed → offsets table needs a new block |
| symbol address shifted | code around that symbol changed → check Apple advisories |
| syscall count changed | syscalls added/removed → new attack surface |
| item went UNRESOLVED | a field or function vanished → investigate |
| kernel base / entry moved | KASLR layout change → relevant for exploit geometry |

---

## Status

| board | SoC | device | last build | report |
|-------|-----|--------|------------|--------|
| t8030 | A13 | iPhone SE 2 | 26.6.1 (23G83) | [reports/t8030-26.6.1-23G83.md](reports/t8030-26.6.1-23G83.md) |
| t8110 | A15 | iPhone 14 | 26.6.1 (23G83) | [reports/t8110-26.6.1-23G83.md](reports/t8110-26.6.1-23G83.md) |

Baseline (2026-08-25): 26.6 (23G71) → 26.6.1 (23G83), xnu
12377.162.13~2 → 12377.162.14~4, on both boards. t8030: 53 identical,
12 symbol addresses shifted, zero struct moves. t8110: 53 identical, 13
shifted, zero struct moves. `task.itk_space` 0x310 and `proc.struct_size`
0x750 verified on both.

The resolved set covers **65–66 offsets per build**: base/translation
globals, physmap, proc/task/vm_map struct fields, trust cache, sandbox
counts, and the extended symbols (`pmap_bootstrap`, `phystokv`,
`arm_vm_init`, `fatal_error_fmt`, `iorvbar`, `task_collect_crash_info`,
`proc_get_syscall_filter_mask_size`, …). `proc.p_name` resolves per board
(t8030: 0x470 · t8110: 0x488 — see `kcwatch verify`: W0lfSword's offsets.m
26.x block still lists 0x57d).

The comparison table (`kexploit/offsets.m`) is vendored from W0lfSword;
re-sync it whenever W0lfSword's table changes:
`cp <W0lfSword>/kexploit/offsets.m kexploit/offsets.m`.

Adding a board is one config line in scripts/kcwatch.py — t8103 (A14) is
already defined, just enable it in the workflow.

## How it works

```
ipsw.me ──► poll for new signed build
                 │
                 ▼
        fetch kernelcache only        (HTTP Range, ≈20 MB of 8.45 GB, CRC-verified)
                 │
                 ▼
        resolve with XPF              (host-side patchfinder, IMG4 + filesets)
                 │
                 ▼
        diff vs previous build        (struct offsets / constants / symbols)
                 │
                 ▼
        report + feed + atom + HTML   (committed automatically)
```

The pipeline is [`scripts/kcwatch.py`](scripts/kcwatch.py) and runs daily at
06:00 UTC via [GitHub Actions](.github/workflows/watch.yml). It's built on the
[W0lfSword](https://github.com/kaffeindecaf/W0lfSword) iOS toolkit and shares
its offset tables — so a **NO** verdict here is a direct signal for anyone
maintaining exploit offsets.

---

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
python3 scripts/kcwatch.py poll --board t8030   # fetch → resolve → diff → report
python3 scripts/kcwatch.py verify --board t8030 # is the offsets table still valid?
python3 scripts/kcwatch.py index                # render kernel-deltas.md
python3 scripts/kcwatch.py atom                 # render atom.xml
```

Needs the prebuilt [`tools/xpf-cli`](tools/xpf-cli/README.md) and `liblzfse1`.

---

## Repo layout

```
kernel-deltas.md      the feed index (regenerated each run)
atom.xml              RSS/Atom feed
reports/              one markdown report per release pair
state/<board>/        raw XPF dumps + watcher state (the evidence)
scripts/              kcwatch.py (orchestrator) · kczip.py (ranged fetch) · xpf_diff.py
tools/xpf-cli/        the prebuilt patchfinder (source + shims + binary)
.github/workflows/    the daily cron
```

---

## FAQ

**Does this run on a device?** No. Everything is host-side against Apple's
CDN — that's the whole point.

**"Identical" means safe, right?** No. Identical offsets = same layout,
nothing more. It says nothing about exploitability.

**Why per-board?** Offsets can differ per SoC within the same build. Every
report states its board; a t8030 result doesn't transfer to another SoC
without checking.

**What is "degraded"?** An item that went from resolved → unresolved between
builds. Usually means the structure changed; sometimes it's a PPL item that
never resolves (expected in every build).

**A new iOS dropped and there's no report yet?** The cron runs daily at
06:00 UTC — check the [workflow runs](https://github.com/kaffeindecaf/kernel-deltas/actions).

**Can I add a board?** One line in `scripts/kcwatch.py` (`t8103` is already
defined), plus a loop entry in the workflow. t8103 (A14) is the natural next
one.

---

## Glossary

| term | plain meaning |
|---|---|
| **kernelcache** | the compressed kernel + its data, inside every IPSW |
| **offset** | "where in the struct is field X" — the number exploit code adds to a struct pointer |
| **offset table** | the per-iOS list of those numbers (offsets.m in W0lfSword) |
| **XPF** | a host-side patchfinder: finds offsets by scanning the kernel image, no device needed |
| **IMG4** | the signed container format the kernelcache ships in |
| **fileset** | modern iOS splits the kernel into pieces; filesets are the pieces |
| **SPTM** | the SoC's "secure page table monitor" — a chunk of the kernel lives behind it |
| **t8030 / t8110** | Apple SoC codenames: A13 / A15 |
| **xnu** | the kernel itself (its version string is per-build) |

---

## Caveats

- Reports describe *layout*, not *vulnerability*. Same offsets ≠ exploitable.
- Apple advisories land after releases. This feed is the "before" half.
- A handful of PPL items read UNRESOLVED in every build — expected, not a regression.

---

## Credits

- XPF patchfinder + pipeline: [W0lfSword](https://github.com/kaffeindecaf/W0lfSword) (`tools/xpf-cli`)
- Ranged-fetch technique proven against real Apple CDN IPSWs during the K4.1
  offset verification
- Release metadata: [ipsw.me](https://ipsw.me) API
