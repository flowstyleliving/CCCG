"""Build a self-contained HTML trace viewer for one run folder (offline; no key).

    python3 -m msraf.viewer runs/main15-2026-11-16            # writes runs/main15-2026-11-16/viewer.html
    python3 -m msraf.viewer runs/my-run --out /tmp/my-run.html

The page embeds every episode's scores, judge verdicts, message events and final report,
so it opens straight from disk with no server or network.
"""

import argparse
import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("viewer.html")
SCORE_FILES = ("score_v2.json", "score.json")  # same preference as msraf.analyze
EVENT_KEYS = ("kind", "stakeholder", "text", "sent_turn", "due_turn", "delivered_turn", "seen_turn", "status", "follow_up")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_episode(d):
    meta, end, events = _read(d / "meta.json"), _read(d / "end.json"), _read(d / "events.json")
    score_file = next((f for f in SCORE_FILES if (d / f).exists()), None)
    score = _read(d / score_file) if score_file else {}
    # Older runs record no spec in meta.json; the opening message always comes from the point person.
    point = (meta.get("spec") or {}).get("point_person", {}).get("option") \
        or next((e["stakeholder"] for e in events if e["kind"] == "opening"), None)
    return {
        "id": d.name, "model": d.name.rsplit("_cf", 1)[0], "agent_model": meta.get("agent_model"),
        "cf": bool(meta["cf"]), "ap": bool(meta["ap"]), "seed": meta.get("seed"),
        "max_turns": meta.get("max_turns"), "point": point,
        "turn": end.get("turn"), "finished": end.get("finished"), "hit_guard": end.get("hit_guard"),
        "termination": end.get("termination") or ("finished" if end.get("finished") else "not finished"),
        "report": end.get("report"), "score_file": score_file,
        "scores": score.get("scores"), "verdicts": score.get("verdicts") or {},
        "events": [{k: e.get(k) for k in EVENT_KEYS} for e in events],
    }


def collect(run_dir):
    run_dir = Path(run_dir)
    episodes = [load_episode(d) for d in sorted(run_dir.iterdir()) if (d / "end.json").exists()]
    if not episodes:
        raise SystemExit(f"{run_dir}: no episode folders (subfolders with end.json) found")
    return episodes


def render(run_dir, episodes):
    data = json.dumps({"run": Path(run_dir).name, "episodes": episodes}, ensure_ascii=False)
    # Inside <script>, "</" could close the tag early; "<\/" is the same JSON string.
    return TEMPLATE.read_text(encoding="utf-8").replace("__TRACE_DATA__", data.replace("</", "<\\/"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run", type=Path, help="run folder, e.g. runs/main15-2026-11-16")
    parser.add_argument("--out", type=Path, help="output HTML (default: <run>/viewer.html)")
    args = parser.parse_args()
    out = args.out or args.run / "viewer.html"
    episodes = collect(args.run)
    out.write_text(render(args.run, episodes), encoding="utf-8")
    print(f"{out}  ({len(episodes)} episodes)")


if __name__ == "__main__":
    main()
