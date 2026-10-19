LILITH SCENARIO BUILDER — PORTABLE SKILL PACKAGE
Version 1.0 — 19 October 2026

WHAT'S INSIDE
  SKILL.md
    Skill identity, when to activate it, workflow, and artifact contract.
  references/LILITH_SCENARIO_INSTRUCTIONS.txt
    Complete Lilith scenario creation specification.
  scripts/validate_scenario.py
    Standard-library Python CLI validator for paired TXT/JSON scenario outputs.
  examples/Night_Shift_at_Blackwood_Scenario.txt
  examples/Night_Shift_at_Blackwood_Story_Cards.json
    A five-card demonstration pair that passes the offline validator; examples
    are not default Lilith story canon and should not be copied indiscriminately.
  scripts/merge_story_cards.py
    Safe export-plus-additions merge helper (blocks unapproved replacements).

HOW TO USE
1. Keep the folder structure intact when adding the skill to an environment
   that supports folder-based Agent Skills.
2. If your platform supports skills, import/install this skill package through
   that platform's own skill interface or copy the folder into its configured
   skill location. Exact steps depend on platform and may differ over time.
3. If your ChatGPT interface does not expose skill installation, attach the
   standalone LILITH_SCENARIO_INSTRUCTIONS.txt to a project or conversation
   and paste SKILL.md as custom assistant/project instructions, subject to
   the size and feature limits of your chosen interface.
4. Supply a scenario idea or your existing scenario TXT and exported cards.
5. Ask for CREATE, REVISE, EXPAND, MERGE, AUDIT, or VALIDATE.

EXAMPLE REQUEST
"Create a Lilith Free Roam scenario set in a contemporary university city.
Use Balanced context. Include six NPCs, five locations, a player setup and a
playable opening. Output the scenario TXT and AID Story Cards JSON."

VALIDATION
python scripts/validate_scenario.py Example_Scenario.txt Example_Story_Cards.json

Add --allow-legacy only when auditing or merging pre-Lilith cards that you
must preserve unchanged. It downgrades Lilith-only card content constraints
to warnings; it does not waive TXT/JSON matching or JSON validity.

The skill produces ordinary Simple Start Story Card JSON with keys, value,
type, title and description. Character Creator-specific flags are omitted
by default because public example/prose spellings conflict. Existing custom
export fields are preserved without modification in safe merges.

IMPORTANT AID IMPORT SAFETY
Importing a Story Card JSON file REPLACES the entire card collection. Back
up existing cards and create a full merged export rather than importing an
add-on JSON by itself. AID's import/export UI is documented for web.

This is a portable skill asset, not a claim that a skill has been installed
or registered inside your ChatGPT account or AI Dungeon.

SAFE JSON MERGE
python scripts/merge_story_cards.py existing.json additions.json full_merged.json

To replace an existing named card explicitly:
python scripts/merge_story_cards.py existing.json additions.json full_merged.json --replace "Character::Mira Collins"

This command only merges JSON. Regenerate the FULL matching scenario TXT
from the resulting JSON using the Skill afterwards.
