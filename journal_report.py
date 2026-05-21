"""Detailed report on the recommendation journal.

Scores any still-open entries against the latest prices, then prints the
overall and per-track realized track record plus the most recent closed trades.
Run it any time to see how the scanner's past recommendations actually did.

Usage:
    python journal_report.py [n_recent]
"""
import os
import sys

import revolut_scanner_v13 as rs
from scanner.journal import load_journal, score_open_entries, summarize_journal

N_RECENT = int(sys.argv[1]) if len(sys.argv) > 1 else 25


def main():
    path = os.path.join(rs.OUTDIR, rs.JOURNAL_CSV)
    if not os.path.exists(path):
        print(f"No journal yet at {path}. Run a scan first to start logging.")
        return
    rows = score_open_entries(path, lambda t: rs.download_history(t))
    s = summarize_journal(rows)

    print("RECOMMENDATION JOURNAL REPORT")
    print("=" * 78)
    print(f"logged {s['total_logged']}  ·  open {s['open']}  ·  closed {s['closed']}")
    ov = s["overall"]
    if ov:
        print(f"\nOverall (closed): n={ov['n']}  win rate {ov['win_rate']:.1f}%  "
              f"avg {ov['avg_realized']:+.2f}%  total {ov['total_realized']:+.2f}%  "
              f"TP/SL/time {ov['tp']}/{ov['sl']}/{ov['time']}")
    if s["per_track"]:
        print("\nPer track:")
        print(f"  {'track':<22}{'n':>5}{'win%':>8}{'avg%':>9}{'total%':>10}{'TP/SL/T':>12}")
        for t, st in s["per_track"].items():
            tpsl = f"{st['tp']}/{st['sl']}/{st['time']}"
            print(f"  {t:<22}{st['n']:>5}{st['win_rate']:>7.1f}%{st['avg_realized']:>+8.2f}%"
                  f"{st['total_realized']:>+9.2f}%{tpsl:>12}")

    closed = [r for r in rows if r.get("status") == "closed"]
    closed.sort(key=lambda r: r.get("exit_date", ""), reverse=True)
    if closed:
        print(f"\nMost recent {min(N_RECENT, len(closed))} closed trades:")
        print(f"  {'exit':<12}{'track':<16}{'ticker':<14}{'outcome':>8}{'realized%':>11}{'days':>6}")
        for r in closed[:N_RECENT]:
            print(f"  {r.get('exit_date',''):<12}{r.get('track',''):<16}{r.get('ticker',''):<14}"
                  f"{r.get('outcome',''):>8}{float(r.get('realized_pct',0)):>+10.2f}%"
                  f"{r.get('days_held',''):>6}")

    if not closed:
        print("\nNo closed trades yet — outcomes appear as positions hit TP/SL or time out.")


if __name__ == "__main__":
    main()
