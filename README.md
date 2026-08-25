# kernel-deltas

What changed in the iOS kernel between builds. Resolved offsets and symbols, diffed per release, published as plain markdown.

Watching t8030 (A13, iPhone SE 2) since 2026-08-25. Every new signed release is fetched, resolved, diffed and reported within hours of Apple shipping it. No devices involved, no jailbreaks, no 8GB downloads.

## Why this exists

When a new iOS build drops, the first question for anyone doing kernel work is: did anything move? The old way was find the IPSW, download 6-8GB, extract the kernelcache, resolve it, and diff against the last build by hand. This repo does the whole loop automatically and publishes the result.

## How it works

1. Poll the ipsw.me release feed for the watched board.
2. Pull only the kernelcache entry out of the IPSW with HTTP Range requests. The entry is about 20MB; the IPSW it lives in is 8.45GB. Fetch, CRC-verify, decompress, done.
3. Resolve the offset table with XPF, a host-side patchfinder that runs on the raw IMG4 and knows about SPTM and filesets.
4. Diff against the previous build and write a report.

The pipeline is scripts/ in this repo, built on the W0lfSword toolkit. It runs daily via GitHub Actions.

## Reading a report

The short version is the verdict line at the bottom of each report:

```
VERDICT: YES. offsets.m block '>= 26.0' applies to 26.6.1 (all struct/constant
offsets identical to previous build)
```

The rest of the report is the evidence:

- kernel identity: xnu build and Darwin version of both sides
- counts: identical, changed, degraded and one-sided items across the resolved offset table
- the changed items with old and new addresses
- items that went UNRESOLVED, which usually means a structural change

What each signal means:

| signal | meaning |
|--------|---------|
| struct offset moved | kernel struct layout changed, the offsets table needs a new version block |
| symbol address shifted | code around that symbol changed, cross-reference it against Apple advisories |
| syscall count changed | syscalls added or removed, new attack surface |
| item went UNRESOLVED | field or function vanished, investigate |
| kernel base or entry moved | KASLR layout change, relevant for exploit geometry |

## Status

| board | SoC | device | last build | report |
|-------|-----|--------|------------|--------|
| t8030 | A13 | iPhone SE 2 | 26.6.1 (23G83) | [reports/t8030-26.6.1-23G83.md](reports/t8030-26.6.1-23G83.md) |

Baseline diff (2026-08-25): 26.6 (23G71) to 26.6.1 (23G83), xnu 12377.162.13~2 to 12377.162.14~4. 51 items identical, 12 symbol addresses shifted, zero struct moves.

Adding a board is one config line in scripts/kcwatch.py. t8103 (A14) and t8110 (A15) are already defined; enable them in .github/workflows/watch.yml when you want them watched.

## Run it yourself

The pipeline ships in W0lfSword:

```
git clone https://github.com/kaffeindecaf/W0lfSword
cd W0lfSword
./W0lfSword kcwatch poll --board t8030
```

Or directly, without the wrapper:

```
python3 scripts/kcwatch.py poll --board t8030
```

Needs the prebuilt xpf-cli (tools/xpf-cli) and liblzfse1.

## Caveats

- Identical offsets are not exploitability. Same layout, nothing more.
- Offsets can differ per SoC within one build. Reports state the board; a t8030 result does not transfer to another SoC without checking.
- A few PPL items come back UNRESOLVED in every build. Expected, not a regression.
- Apple's security advisories land after the release. This feed is the before half of the picture.

## Credits

- XPF patchfinder and the pipeline: [W0lfSword](https://github.com/kaffeindecaf/W0lfSword) (tools/xpf-cli)
- Ranged-fetch technique proven against real Apple CDN IPSWs during the K4.1 offset verification
- Release metadata: [ipsw.me](https://ipsw.me) API
