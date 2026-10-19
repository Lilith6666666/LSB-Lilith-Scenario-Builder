#!/usr/bin/env python3
"""Safely merge an existing AID Story Card export with newly authored card objects.

Does not silently replace existing same-identity cards. Outputs a FULL array
for import; a separate Lilith scenario TXT must be regenerated to match it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a top-level JSON array")
    for i, card in enumerate(data, 1):
        if not isinstance(card, dict) or any(not isinstance(card.get(k), str) or not card[k].strip() for k in ("keys", "value")):
            raise ValueError(f"{path}: card {i} needs nonempty string keys and value")
    return data


def identity(card: dict) -> str | None:
    name = card.get("title")
    kind = card.get("type")
    if not isinstance(name, str) or not name.strip() or not isinstance(kind, str) or not kind.strip():
        return None
    return f"{kind.strip()}::{name.strip()}".casefold()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("existing", type=Path, help="FULL existing AID export")
    p.add_argument("additions", type=Path, help="JSON array of proposed new or changed cards")
    p.add_argument("output", type=Path, help="Destination FULL merged import file")
    p.add_argument("--replace", action="append", default=[], metavar="TYPE::TITLE", help="Explicitly permit replacement of this same-identity card; repeatable")
    a = p.parse_args()
    if a.output.resolve() in {a.existing.resolve(), a.additions.resolve()}:
        print("ERROR: output must not overwrite an input; preserve your original export as a backup")
        return 2
    if a.output.exists():
        print("ERROR: output already exists; choose a new path to avoid accidental overwrite")
        return 2
    try:
        original, additions = load(a.existing), load(a.additions)
    except ValueError as exc:
        print("ERROR:", exc)
        return 2

    result = [dict(card) for card in original]
    by_id = {}
    for i, card in enumerate(result):
        card_id = identity(card)
        if card_id:
            by_id.setdefault(card_id, []).append(i)
    approved = {r.strip().casefold() for r in a.replace}
    errors = []
    warnings = []
    num_added = num_replaced = num_skipped = 0
    for incoming in additions:
        target_id = identity(incoming)
        exact_duplicate = next((i for i, c in enumerate(result) if c["keys"] == incoming["keys"] and c["value"] == incoming["value"]), None)
        if exact_duplicate is not None:
            num_skipped += 1
            if incoming != result[exact_duplicate]:
                warnings.append(f"Kept existing metadata for duplicate keys+Entry on card {incoming.get('title', incoming['keys'])}")
            continue
        matches = by_id.get(target_id, []) if target_id else []
        if len(matches) > 1:
            errors.append(f"Multiple existing cards share identity {target_id}; manual resolution required")
            continue
        if matches:
            if target_id not in approved:
                errors.append(f"Existing card conflicts with addition {target_id}; require --replace {target_id}")
                continue
            i = matches[0]
            result[i] = {**result[i], **incoming}  # preserve unknown fields unless explicitly overridden
            num_replaced += 1
        else:
            # If keys are the same but Entry differs, this is a potentially destructive/ambiguous identity.
            for old in result:
                if old["keys"].strip().casefold() == incoming["keys"].strip().casefold():
                    errors.append(f"Ambiguous identical triggers with different Entries: {incoming['keys']!r}; review manually")
                    break
            else:
                result.append(dict(incoming))
                num_added += 1
                if target_id:
                    by_id[target_id] = [len(result) - 1]

    if errors:
        for error in errors:
            print("ERROR:", error)
        print("ABORTED: no output written; original cards unchanged")
        return 1
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for warning in warnings:
        print("WARNING:", warning)
    print(f"PASS: {len(original)} existing + {num_added} additions + {num_replaced} approved replacements = {len(result)} full cards; {num_skipped} duplicates skipped")
    print("Output:", a.output)
    print("Importing the result REPLACES the whole card set; BACK UP the AID scenario first.")
    print("Regenerate a full matching scenario TXT before claiming a complete Lilith paired export.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
