#!/usr/bin/env python3
"""Validate a Lilith v1 paired scenario TXT / AI Dungeon Story Cards JSON.

Pure standard-library validator. Checks structure and exact mirrored cards;
creative consistency still needs a human/model review and a live AID playtest.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SECTION_HEADINGS = [
    "=== LILITH SCENARIO PACKAGE ===",
    "=== SCENARIO DETAILS ===",
    "=== OPENING PROMPT ===",
    "=== PLOT ESSENTIALS ===",
    "=== AI INSTRUCTIONS ===",
    "=== AUTHOR'S NOTE ===",
    "=== STORY CARDS ===",
    "=== DEPLOYMENT NOTES ===",
]
PLAYER_FIELDS = [
    "First Name", "Last Name", "Age", "Gender", "Pronouns",
    "Physical Appearance", "Bio",
]
TYPE_FIELDS = {
    "character": ["First Name", "Last Name", "Age", "Gender", "Appearance", "Personality", "Role"],
    "location": ["Name", "Type", "Region/Setting", "Appearance/Atmosphere", "Key Features"],
    "faction": ["Name", "Type", "Goal", "Organization/Leader", "Methods"],
    "item": ["Name", "Type", "Appearance", "Function", "Limits/Cost"],
    "lore": ["Name", "Definition", "Scope", "Constraints/Consequences"],
    "concept": ["Name", "Definition", "Scope", "Constraints/Consequences"],
    "rule": ["Name", "Definition", "Scope", "Constraints/Consequences"],
}
BLOCK_RE = re.compile(
    r"(?ms)^=== STORY CARD (\d{3}) ===\n(.*?)^=== END STORY CARD ===\s*(?=^=== STORY CARD \d{3} ===|\Z)"
)


def normalize(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def read_utf8(path: Path) -> str:
    return normalize(path.read_text(encoding="utf-8-sig"))


def parse_txt_cards(text: str, errors: list[str]) -> list[dict[str, str]]:
    try:
        part = text.split("=== STORY CARDS ===\n", 1)[1]
        part = part.split("=== DEPLOYMENT NOTES ===", 1)[0]
    except IndexError:
        errors.append("Missing STORY CARDS or DEPLOYMENT NOTES boundary")
        return []

    cards = []
    matches = list(BLOCK_RE.finditer(part))
    if not matches:
        if part.strip() == "(none)":
            return []
        errors.append("STORY CARDS section has no correctly delimited blocks; use STORY CARD 001 / END STORY CARD")
        return []

    leftovers = BLOCK_RE.sub("", part).strip()
    if leftovers:
        errors.append("Unparsed text exists inside STORY CARDS section (bad delimiter or stray content): " + repr(leftovers[:130]))

    for index, match in enumerate(matches, 1):
        number = int(match.group(1))
        if number != index:
            errors.append(f"Story Card block numbering must be consecutive starting 001; found {number:03d} in position {index}")
        block = match.group(2).rstrip("\n")
        lines = block.split("\n")
        if len(lines) < 6:
            errors.append(f"TXT Story Card {number:03d} is incomplete")
            continue
        expected = ("Title: ", "Type: ", "Triggers: ", "Notes: ", "Entry:")
        for i, prefix in enumerate(expected):
            if i == 4 and lines[i] != "Entry:":
                errors.append(f"TXT Story Card {number:03d} needs an exact 'Entry:' line")
            elif i < 4 and not lines[i].startswith(prefix):
                errors.append(f"TXT Story Card {number:03d} needs '{prefix}' on line {i + 1}")
        if any(not lines[i].startswith(expected[i]) for i in range(4)) or lines[4] != "Entry:":
            continue
        cards.append({
            "title": lines[0][7:],
            "type": lines[1][6:],
            "keys": lines[2][10:],
            "description": lines[3][7:],
            "value": "\n".join(lines[5:]),
        })
    return cards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("txt", type=Path, help="Complete Lilith scenario TXT")
    parser.add_argument("json_file", type=Path, help="AID Story Cards JSON array")
    parser.add_argument("--allow-legacy", action="store_true", help="Warn rather than error for missing Lilith type-specific Entry fields")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    try:
        txt = read_utf8(args.txt)
        raw_json = read_utf8(args.json_file)
    except (OSError, UnicodeError) as exc:
        print("ERROR: Cannot open a UTF-8 input file:", exc)
        return 2
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
        return 2
    if not isinstance(payload, list):
        print("ERROR: AI Dungeon Story Card JSON must be one top-level array")
        return 2

    headings_found = []
    for heading in SECTION_HEADINGS:
        n = txt.count(heading)
        if n != 1:
            errors.append(f"Expected exactly one section heading {heading!r}; found {n}")
        pos = txt.find(heading)
        if pos >= 0:
            headings_found.append(pos)
    if headings_found != sorted(headings_found):
        errors.append("Required TXT sections are not in the specified order")

    if txt.count("[PLAYER SETUP]") != 1 or txt.count("[/PLAYER SETUP]") != 1:
        errors.append("PLOT ESSENTIALS must contain exactly one [PLAYER SETUP] block")
    try:
        plot_section = txt.split("=== PLOT ESSENTIALS ===\n", 1)[1].split("=== AI INSTRUCTIONS ===", 1)[0]
    except IndexError:
        plot_section = ""
    player_match = re.search(r"(?s)\[PLAYER SETUP\]\n(.*?)\n\[/PLAYER SETUP\]", plot_section)
    if player_match:
        labels = []
        for line in player_match.group(1).splitlines():
            if ":" in line:
                label, value = line.split(":", 1)
                labels.append(label.strip())
                if label.strip() in PLAYER_FIELDS and not value.strip():
                    errors.append(f"Player Setup value for {label.strip()} is empty")
        if labels != PLAYER_FIELDS:
            errors.append("Player Setup fields must match the required seven labels in the specified order")
    else:
        errors.append("Invalid PLAYER SETUP delimiters/line breaks, or block is outside PLOT ESSENTIALS")

    try:
        ain = txt.split("=== AI INSTRUCTIONS ===\n", 1)[1].split("=== AUTHOR'S NOTE ===", 1)[0]
        if re.search(r"\$\{[^\n{}]*\}", ain):
            errors.append("AI Instructions contain `${...}`; scenario placeholders should be in supported components")
    except IndexError:
        pass

    for section in ("=== OPENING PROMPT ===", "=== PLOT ESSENTIALS ===", "=== AUTHOR'S NOTE ==="):
        try:
            idx = SECTION_HEADINGS.index(section)
            content = txt.split(section + "\n", 1)[1].split(SECTION_HEADINGS[idx + 1], 1)[0]
            if not content.strip():
                errors.append(f"Empty required TXT section: {section}")
        except IndexError:
            pass

    for i, card in enumerate(payload, 1):
        if not isinstance(card, dict):
            errors.append(f"JSON Story Card {i} is not an object")
            continue
        for name in ("keys", "value"):
            if not isinstance(card.get(name), str) or not card[name].strip():
                errors.append(f"JSON Story Card {i} has missing/empty string {name!r}")
        for name in ("title", "type", "description"):
            if name in card and not isinstance(card[name], str):
                errors.append(f"JSON Story Card {i} has non-string {name!r}")
        for creator_flag in ("useForCharacterCreator", "useForCharacterCreation"):
            if creator_flag in card:
                if not isinstance(card[creator_flag], bool):
                    errors.append(f"JSON Story Card {i} has non-boolean {creator_flag}")
                else:
                    warnings.append(f"Card {i} uses legacy/ambiguous {creator_flag}; preserve for merges, but omit for new Simple Start cards")
        forbidden = {"pinned", "spoilers", "scriptState", "lilith", "metadata"}
        disallowed = forbidden.intersection(card.keys())
        if disallowed:
            errors.append(f"JSON Story Card {i} includes speculative unsupported field(s): {sorted(disallowed)}")
        keys = card.get("keys", "")
        if isinstance(keys, str):
            if any(not token.strip() for token in keys.split(",")):
                errors.append(f"JSON Story Card {i} has an empty comma-separated trigger")
            generic = {"you", "i", "he", "she", "school", "friend", "person", "town"}
            for trigger in keys.split(","):
                if trigger.strip().casefold() in generic:
                    warnings.append(f"Card {i} has a broad trigger {trigger.strip()!r}; check accidental activation")

        val = card.get("value", "")
        card_type = card.get("type", "")
        if isinstance(val, str) and isinstance(card_type, str):
            if card.get("title") and isinstance(card["title"], str) and card["title"].casefold() not in val.casefold():
                warnings.append(f"Card {i} title is not visibly repeated inside its Entry; ensure the entity is identified")
            required = TYPE_FIELDS.get(card_type.casefold(), [])
            missing = [f for f in required if not re.search(r"(?<![A-Za-z])" + re.escape(f) + r":\s*\S", val)]
            if missing:
                issue = f"JSON Story Card {i} ({card.get('title', 'untitled')}) missing Lilith {card_type} Entry fields: {', '.join(missing)}"
                (warnings if args.allow_legacy else errors).append(issue)

    if len(payload) == 0:
        warnings.append("JSON array is empty: importing [] into AID would ERASE existing Story Cards")

    txt_cards = parse_txt_cards(txt, errors)
    if len(txt_cards) != len(payload):
        errors.append(f"TXT/JSON card count differs: TXT has {len(txt_cards)}, JSON has {len(payload)}")
    for i, (left, right) in enumerate(zip(txt_cards, payload), 1):
        if not isinstance(right, dict):
            continue
        for field in ("title", "type", "keys", "description", "value"):
            if left[field] != right.get(field, ""):
                errors.append(f"TXT/JSON Story Card {i} differs in {field!r}")

    seen_duplicates: dict[tuple[str, str], int] = {}
    trigger_to_titles: dict[str, set[str]] = defaultdict(set)
    for i, c in enumerate(payload, 1):
        if not isinstance(c, dict):
            continue
        keys, value = c.get("keys"), c.get("value")
        if isinstance(keys, str) and isinstance(value, str):
            pair = (keys, value)
            if pair in seen_duplicates:
                errors.append(f"Exact duplicate JSON cards {seen_duplicates[pair]} and {i}")
            seen_duplicates[pair] = i
            for k in keys.split(","):
                if k.strip():
                    trigger_to_titles[k.strip().casefold()].add(str(c.get("title", i)))
    for trigger, titles in trigger_to_titles.items():
        if len(titles) > 1:
            warnings.append(f"Trigger {trigger!r} appears on multiple distinct card titles: {', '.join(sorted(titles))}")

    print(f"Lilith paired export validation: {args.txt.name} + {args.json_file.name}")
    print(f"Story Cards: {len(payload)} JSON / {len(txt_cards)} TXT")
    for issue in errors:
        print("ERROR:", issue)
    for issue in warnings:
        print("WARNING:", issue)
    if errors:
        print(f"FAIL: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: file syntax and TXT/JSON structure match ({len(warnings)} warning(s)). Live AID import/gameplay NOT tested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
