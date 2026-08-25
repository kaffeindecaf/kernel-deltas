#!/usr/bin/env python3
"""Regenerate kernel-deltas state/reports/feed/dashboard from freshly
re-resolved dumps (extended XPF set: proc.p_name, task.threads_next,
10 extended symbols). Run from the repo root after the four .txt dumps
exist under .kcwatch/<board>/."""
import json, os, re, sys, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import kcwatch

BASE = os.path.join(REPO, ".kcwatch")

def xnu_of(dump):
    hdr, _ = kcwatch.parse_dump(dump)
    return hdr.get("xnu", "?")

def release_dates():
    """board -> {version: releasedate} from ipsw.me."""
    out = {}
    for board, cfg in kcwatch.BOARDS.items():
        try:
            data = json.load(urllib.request.urlopen(kcwatch.IPSW_ME % cfg["device"], timeout=30))
        except Exception:
            out[board] = {}
            continue
        d = {}
        for f in (data.get("releases") or data.get("firmwares") or []):
            if f.get("version") in ("26.6", "26.6.1"):
                d[f["version"]] = f.get("releasedate") or f.get("date") or ""
        out[board] = d
    return out

def main():
    dates = release_dates()
    boards = ["t8030", "t8110"]
    pairs = {b: [("26.6", "23G71"), ("26.6.1", "23G83")] for b in boards}
    all_rows = []

    for b in boards:
        st = {"board": b, "last": None, "history": []}
        for ver, bid in pairs[b]:
            dump = os.path.join(BASE, b, "%s-%s.txt" % (ver, bid))
            if not os.path.isfile(dump):
                print("MISSING %s" % dump)
                return 1
            print("using %s" % dump)
        # baseline = first (26.6), diff = 26.6 -> 26.6.1
        a, bver = pairs[b]
        a_dump = os.path.join(BASE, b, "%s-%s.txt" % (a[0], a[1]))
        b_dump = os.path.join(BASE, b, "%s-%s.txt" % (bver[0], bver[1]))
        d = kcwatch.summarize_diff(a_dump, b_dump)
        verdict = kcwatch.offsets_verdict(bver[0], d)
        cfg = kcwatch.BOARDS[b]
        report = kcwatch.render_report(cfg, {"version": bver[0], "buildid": bver[1]}, st["last"], d, verdict)
        rdir = os.path.join(BASE, b, "reports")
        os.makedirs(rdir, exist_ok=True)
        rfile = os.path.join(rdir, "%s-%s-%s.md" % (b, bver[0], bver[1]))
        with open(rfile, "w") as fh:
            fh.write(report)

        # history: baseline entry (no diff) + latest entry (with diff summary)
        hist = [
            {
                "version": a[0], "buildid": a[1],
                "date": dates.get(b, {}).get(a[0], ""), "signed": True,
                "dump": ".kcwatch/%s/%s-%s.txt" % (b, a[0], a[1]),
            },
            {
                "version": bver[0], "buildid": bver[1],
                "date": dates.get(b, {}).get(bver[0], ""), "signed": True,
                "dump": ".kcwatch/%s/%s-%s.txt" % (b, bver[0], bver[1]),
                "xnu": d.get("xnu_b", "?"),
                "identical": len(d["identical"]), "changed": len(d["changed"]),
                "degraded": len(d["degraded"]), "verdict": verdict,
            },
        ]
        st["last"] = hist[-1]
        st["history"] = hist
        with open(os.path.join(BASE, b, "state.json"), "w") as fh:
            json.dump(st, fh, indent=2)
            fh.write("\n")
        print("%s: %d identical / %d changed / %d degraded — %s" % (
            b, len(d["identical"]), len(d["changed"]), len(d["degraded"]),
            verdict.split(".")[0]))
        print("  report: %s" % rfile)

    # sync into state/ + reports/ (the committed layout)
    for b in boards:
        for ver, bid in pairs[b]:
            src = os.path.join(BASE, b, "%s-%s.txt" % (ver, bid))
            dst = os.path.join(REPO, "state", b, "%s-%s.txt" % (ver, bid))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src, "rb") as f, open(dst, "wb") as g:
                g.write(f.read())
        with open(os.path.join(BASE, b, "state.json")) as f, \
             open(os.path.join(REPO, "state", b, "state.json"), "w") as g:
            g.write(f.read())
        for fn in os.listdir(os.path.join(BASE, b, "reports")):
            with open(os.path.join(BASE, b, "reports", fn)) as f, \
                 open(os.path.join(REPO, "reports", fn), "w") as g:
                g.write(f.read())
    print("synced state/ + reports/")
    return 0

if __name__ == "__main__":
    sys.exit(main())
