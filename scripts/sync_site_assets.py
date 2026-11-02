"""Copy the files the report site shows into docs/, because GitHub Pages publishes only the docs/ folder.

Usage, from the repository root:
    python3 scripts/sync_site_assets.py

Copies the BPMN and use case diagrams, the Mermaid sources, the OpenAPI file, the wireframes and any JIRA or
Confluence screenshots into docs/assets/, and writes docs/data/plan.json (story points per epic and sprint) from
agile/jira/jira-import.csv. Large diagrams are scaled to 2400 pixels wide when the macOS tool sips is available.
Standard library only.
"""
import csv
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
COPIES = [
    ("diagrams/bpmn", "*.png", "bpmn"),
    ("diagrams/uml", "00_use_case_diagram.png", "uml"),
    ("diagrams/uml", "*.mmd", "uml"),
    ("api/openapi", "*.yaml", "api"),
    ("design/wireframes", "*.png", "wireframes"),
    ("agile/screenshots", "*.png", "screenshots"),
]
MAX_WIDTH = 2400


def png_width(path):
    with path.open("rb") as f:
        header = f.read(24)
    return int.from_bytes(header[16:20], "big")


def copy_assets():
    copied = 0
    for source, pattern, target in COPIES:
        for file in sorted((ROOT / source).glob(pattern)):
            destination = ASSETS / target / file.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, destination)
            if file.suffix == ".png" and png_width(destination) > MAX_WIDTH and shutil.which("sips"):
                subprocess.run(["sips", "--resampleWidth", str(MAX_WIDTH), str(destination)],
                               check=True, capture_output=True)
            copied += 1
    return copied


def write_plan():
    rows = list(csv.DictReader((ROOT / "agile" / "jira" / "jira-import.csv").open(encoding="utf-8")))
    epics = [{"id": r["Issue Id"], "name": r["Summary"].split(" ", 1)[1], "points": 0, "items": 0}
             for r in rows if r["Issue Type"] == "Epic"]
    by_id = {e["id"]: e for e in epics}
    sprints = {}
    for r in rows:
        if r["Issue Type"] == "Epic":
            continue
        points = int(r["Story Points"])
        by_id[r["Parent Id"]]["points"] += points
        by_id[r["Parent Id"]]["items"] += 1
        sprint = int(r["Sprint"].rsplit(" ", 1)[1])
        entry = sprints.setdefault(sprint, {"sprint": sprint, "points": 0, "items": []})
        entry["points"] += points
        entry["items"].append(r["Issue Id"])
    plan = {"epics": epics, "sprints": [sprints[k] for k in sorted(sprints)],
            "total_points": sum(e["points"] for e in epics), "total_items": sum(e["items"] for e in epics)}
    out = ROOT / "docs" / "data" / "plan.json"
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return plan


if __name__ == "__main__":
    n = copy_assets()
    plan = write_plan()
    print(f"{n} files copied to docs/assets; plan.json: {plan['total_items']} items, {plan['total_points']} points")
