#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


FIELD_MAP = {
    "name": "name",
    "category": "category",
    "pattern": "pattern",
    "target_people": "audience",
    "ingredients": "composition",
    "default_dosage": "default_dosage",
    "usage": "usage",
    "modifications": "modifications",
    "contraindications": "cautions",
    "taste_notes": "taste_notes",
    "cost_notes": "cost_notes",
    "notes": "notes",
    "package_count": "package_count",
    "unit_total_grams": "unit_total_grams",
    "total_grams": "total_grams",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Import formula templates from a JSON file.")
    parser.add_argument("json_file", help="Path to a JSON array or an object with a templates array.")
    parser.add_argument("--update", action="store_true", help="Update existing templates that have the same name.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print actions without writing to SQLite.")
    return parser.parse_args()


def load_templates(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("templates"), list):
        return data["templates"]
    raise ValueError("JSON must be an array or an object with a templates array.")


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def clean_number(value, default=0):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_default_dosage_weight(default_dosage):
    total = 0
    for part in re.split(r"[，,；;、\n]+", default_dosage or ""):
        match = re.search(r"(\d+(?:\.\d+)?)\s*g\b", part.strip(), flags=re.IGNORECASE)
        if match:
            total += float(match.group(1))
    return total


def normalize(raw):
    item = {target: clean_text(raw.get(source)) for source, target in FIELD_MAP.items()}
    package_count = int(clean_number(raw.get("package_count"), 14) or 14)
    unit_total_grams = clean_number(raw.get("unit_total_grams"), 0)
    if not unit_total_grams:
        unit_total_grams = parse_default_dosage_weight(item["default_dosage"])
    total_grams = clean_number(raw.get("total_grams"), 0)
    if not total_grams and unit_total_grams:
        total_grams = unit_total_grams * package_count
    item["package_count"] = package_count
    item["unit_total_grams"] = round(unit_total_grams, 2)
    item["total_grams"] = round(total_grams, 2)
    return item


def import_templates(path, update=False, dry_run=False):
    server.init_db()
    raw_templates = load_templates(path)
    stats = {"created": 0, "updated": 0, "skipped": 0, "invalid": 0}
    messages = []
    now = int(time.time())

    with server.connect() as conn:
        for index, raw in enumerate(raw_templates, start=1):
            if not isinstance(raw, dict):
                stats["invalid"] += 1
                messages.append(f"invalid[{index}]: item is not an object")
                continue

            item = normalize(raw)
            if not item["name"]:
                stats["invalid"] += 1
                messages.append(f"invalid[{index}]: missing required field name")
                continue

            existing = conn.execute(
                "SELECT id FROM formula_templates WHERE name = ?",
                (item["name"],),
            ).fetchone()

            if existing and not update:
                stats["skipped"] += 1
                messages.append(f"skipped[{index}]: {item['name']} already exists")
                continue

            if dry_run:
                action = "update" if existing else "create"
                stats["updated" if existing else "created"] += 1
                messages.append(f"dry_run[{index}]: would {action} {item['name']}")
                continue

            if existing:
                conn.execute(
                    """
                    UPDATE formula_templates
                    SET category = ?, pattern = ?, audience = ?, composition = ?,
                        default_dosage = ?, usage = ?, modifications = ?, cautions = ?,
                        taste_notes = ?, cost_notes = ?, notes = ?, package_count = ?,
                        unit_total_grams = ?, total_grams = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        item["category"],
                        item["pattern"],
                        item["audience"],
                        item["composition"],
                        item["default_dosage"],
                        item["usage"],
                        item["modifications"],
                        item["cautions"],
                        item["taste_notes"],
                        item["cost_notes"],
                        item["notes"],
                        item["package_count"],
                        item["unit_total_grams"],
                        item["total_grams"],
                        now,
                        existing["id"],
                    ),
                )
                stats["updated"] += 1
                messages.append(f"updated[{index}]: {item['name']}")
                continue

            conn.execute(
                """
                INSERT INTO formula_templates
                (id, name, category, pattern, audience, composition, default_dosage,
                 usage, modifications, cautions, taste_notes, cost_notes, notes,
                 package_count, unit_total_grams, total_grams, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"formula_template_{server.secrets.token_hex(8)}",
                    item["name"],
                    item["category"],
                    item["pattern"],
                    item["audience"],
                    item["composition"],
                    item["default_dosage"],
                    item["usage"],
                    item["modifications"],
                    item["cautions"],
                    item["taste_notes"],
                    item["cost_notes"],
                    item["notes"],
                    item["package_count"],
                    item["unit_total_grams"],
                    item["total_grams"],
                    now,
                    now,
                ),
            )
            stats["created"] += 1
            messages.append(f"created[{index}]: {item['name']}")

    return stats, messages


def main():
    args = parse_args()
    try:
        stats, messages = import_templates(args.json_file, update=args.update, dry_run=args.dry_run)
    except Exception as exc:
        print(f"import_failed: {exc}", file=sys.stderr)
        return 1

    for message in messages:
        print(message)
    print(
        "summary: "
        f"created={stats['created']} updated={stats['updated']} "
        f"skipped={stats['skipped']} invalid={stats['invalid']}"
    )
    return 0 if stats["invalid"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
