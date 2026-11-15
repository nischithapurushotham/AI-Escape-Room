"""
Game engine for Version 2.

This file is plain Python. It has NO language model in it.
It holds the rules, the game state and the validation of every action.
The LLM never decides whether an action works. This module does.
"""

import json
import re
from pathlib import Path

ACTIONS = ("examine", "take", "search", "use", "enter_code", "inventory", "help", "unknown")


# ---------------------------------------------------------------------------
# Loading and state
# ---------------------------------------------------------------------------
def load_config(path=None):
    """Read the rules, objects and solutions from game_config.json."""
    path = Path(path) if path else Path(__file__).parent / "game_config.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def new_state(config):
    """The live game state. Only Python code changes it."""
    return {
        "revealed": list(config["start_revealed"]),  # ids the player can see
        "inventory": [],                              # item ids the player carries
        "drawer_open": False,
        "panel_unlocked": False,
        "door_open": False,
        "solved": [],                                 # "drawer", "panel", "door"
        "attempts": 0,                                # wrong codes so far
    }


# ---------------------------------------------------------------------------
# Finding things the player mentions
# ---------------------------------------------------------------------------
def find_entities(text, config):
    """Return [(kind, id), ...] for every known object or item named in text,
    in the order they appear. kind is 'object' or 'item'."""
    text = (text or "").lower()
    found = []
    for kind, group in (("object", config["objects"]), ("item", config["items"])):
        for eid, entry in group.items():
            for alias in entry["aliases"]:
                m = re.search(r"\b" + re.escape(alias) + r"\b", text)
                if m:
                    found.append((m.start(), kind, eid))
    found.sort()
    result, seen = [], set()
    for _, kind, eid in found:
        if (kind, eid) not in seen:
            seen.add((kind, eid))
            result.append((kind, eid))
    return result


def resolve(text, config, kind=None):
    """First known entity in text, optionally only of one kind."""
    for k, eid in find_entities(text, config):
        if kind is None or k == kind:
            return k, eid
    return None


def _entry(config, kind, eid):
    return config["objects" if kind == "object" else "items"][eid]


def _ok(fact):
    return {"ok": True, "fact": fact}


def _fail(fact):
    return {"ok": False, "fact": fact}


def _reveal(state, ids):
    for i in ids:
        if i not in state["revealed"]:
            state["revealed"].append(i)


def _visible(state, hit):
    return hit is not None and hit[1] in state["revealed"]


# ---------------------------------------------------------------------------
# Action handlers. Each one checks the rules, updates the state and returns
# {"ok": True/False, "fact": "what really happened"}.
# ---------------------------------------------------------------------------
def do_examine(intent, state, config):
    hit = resolve(intent.get("target"), config)
    if not intent.get("target"):
        return _fail("The player did not say what to examine.")
    if not _visible(state, hit):
        return _fail(config["messages"]["not_here"])
    kind, eid = hit
    if kind == "item":
        return _ok(config["items"][eid]["text"])
    obj = config["objects"][eid]
    text = obj["description"]
    if eid == "drawer" and state["drawer_open"]:
        text = obj["description_open"]
    if eid == "door" and state["panel_unlocked"]:
        text = obj["description_unlocked"]
    if eid not in ("painting", "drawer"):
        _reveal(state, obj.get("reveals", []))
    return _ok(text)


def do_take(intent, state, config):
    hit = resolve(intent.get("target"), config)
    if not intent.get("target"):
        return _fail("The player did not say what to take.")
    if not _visible(state, hit):
        return _fail(config["messages"]["not_here"])
    kind, eid = hit
    if kind == "object":
        return _fail("That cannot be picked up.")
    name = config["items"][eid]["name"]
    if eid in state["inventory"]:
        return _fail(f"The player already carries the {name}.")
    state["inventory"].append(eid)
    return _ok(f"The player takes the {name}.")


def do_search(intent, state, config):
    hit = resolve(intent.get("target"), config, "object")
    if not intent.get("target"):
        return _fail("The player did not say what to search.")
    if not _visible(state, hit):
        return _fail(config["messages"]["not_here"])
    eid = hit[1]
    if eid == "painting":
        obj = config["objects"]["painting"]
        if "paper_scrap" in state["revealed"]:
            return _ok(obj["search_done_text"])
        _reveal(state, obj["reveals"])
        return _ok(obj["search_text"])
    return _ok(config["messages"]["search_nothing"])


def do_use(intent, state, config):
    combined = f"{intent.get('item') or ''} {intent.get('target') or ''}"
    entities = find_entities(combined, config)
    item_ids = [e for k, e in entities if k == "item"]
    obj_ids = [e for k, e in entities if k == "object"]
    if not item_ids:
        if intent.get("item"):
            return _fail("The player does not have that.")
        return _fail("The player did not say what to use.")
    item_id = item_ids[0]
    if item_id not in state["inventory"]:
        return _fail("The player does not have that item.")
    if not obj_ids:
        return _fail("The player did not say what to use it on.")
    obj_id = obj_ids[0]
    if obj_id not in state["revealed"]:
        return _fail(config["messages"]["not_here"])

    sol = config["solutions"]
    if item_id == sol["key_item"] and obj_id == sol["key_target"]:
        if state["panel_unlocked"]:
            return _fail("The metal panel is already unlocked.")
        state["panel_unlocked"] = True
        state["solved"].append("panel")
        return _ok("The brass key turns in the lock of the metal panel. The panel swings open and shows a four-digit keypad.")
    return _fail("Using that item there has no effect.")


def do_enter_code(intent, state, config):
    code = intent.get("code")
    hit = resolve(intent.get("target"), config, "object")
    if hit is None:
        if intent.get("target"):
            return _fail(config["messages"]["not_here"])
        return _fail("The player did not say where to enter the code.")
    eid = hit[1]
    if eid not in state["revealed"]:
        return _fail(config["messages"]["not_here"])
    sol = config["solutions"]

    if eid == "drawer":
        if state["drawer_open"]:
            return _fail("The drawer is already open.")
        if not code or len(code) != 4:
            return _fail("The drawer has a four-digit combination lock. The player did not give four digits.")
        if code != sol["drawer_code"]:
            state["attempts"] += 1
            return _fail("The combination lock does not open. The code is wrong. The drawer stays locked.")
        state["drawer_open"] = True
        state["solved"].append("drawer")
        _reveal(state, config["objects"]["drawer"]["reveals"])
        return _ok(config["objects"]["drawer"]["unlock_text"])

    if eid == "door":
        if state["door_open"]:
            return _fail("The door is already open.")
        if not state["panel_unlocked"]:
            return _fail("The keypad is behind a locked metal panel. The player cannot reach the keypad yet.")
        if not code or len(code) != 4:
            return _fail("The keypad needs four digits. The player did not give four digits.")
        if code != sol["door_code"]:
            state["attempts"] += 1
            return _fail("The keypad buzzes. The code is wrong. The door stays locked.")
        state["door_open"] = True
        state["solved"].append("door")
        return _ok(config["messages"]["win"])

    return _fail("There is no lock or keypad there.")


def do_inventory(intent, state, config):
    if not state["inventory"]:
        return _ok("The player is carrying nothing.")
    names = [config["items"][i]["name"] for i in state["inventory"]]
    return _ok("The player is carrying: " + ", ".join(names) + ".")


def do_help(intent, state, config):
    return _ok(config["help"])


HANDLERS = {
    "examine": do_examine,
    "take": do_take,
    "search": do_search,
    "use": do_use,
    "enter_code": do_enter_code,
    "inventory": do_inventory,
    "help": do_help,
}


def apply_action(intent, state, config):
    """The one entry point. Anything not in HANDLERS is rejected."""
    handler = HANDLERS.get(intent.get("action"))
    if handler is None:
        result = _fail(config["messages"]["not_possible"])
    else:
        result = handler(intent, state, config)
    result["escaped"] = state["door_open"]
    return result


# ---------------------------------------------------------------------------
# Cleaning the intent that comes from the LLM (or from the fallback parser)
# ---------------------------------------------------------------------------
def clean_intent(raw):
    """Force any parser output into a safe, known shape."""
    if not isinstance(raw, dict):
        return {"action": "unknown", "target": None, "item": None, "code": None}

    def text(v):
        if v is None:
            return None
        v = str(v).strip()
        return v if v and v.lower() != "null" else None

    action = (text(raw.get("action")) or "unknown").lower()
    if action not in ACTIONS:
        action = "unknown"
    code = text(raw.get("code"))
    if code:
        code = re.sub(r"\D", "", code) or None
    return {
        "action": action,
        "target": text(raw.get("target")),
        "item": text(raw.get("item")),
        "code": code,
    }


# ---------------------------------------------------------------------------
# Fallback parser: simple keyword rules, used when the LLM is unavailable.
# It knows no secrets, so it can only point at things the player typed.
# ---------------------------------------------------------------------------
def rule_based_parse(text, config):
    t = (text or "").lower()
    ents = find_entities(t, config)
    items = [e for k, e in ents if k == "item"]
    objs = [e for k, e in ents if k == "object"]
    lock_objs = [o for o in objs if o in ("drawer", "door")]
    m = re.search(r"\b(\d{4})\b", t)
    code = m.group(1) if m else None

    def alias(kind, eid):
        return _entry(config, kind, eid)["aliases"][0]

    if re.search(r"inventory|what do i have|carrying|my items|pockets", t):
        return {"action": "inventory"}
    if re.search(r"\bhelp\b|how do i play|instructions", t):
        return {"action": "help"}
    if code or re.search(r"\b(enter|type|press|input|dial)\b", t):
        target = alias("object", lock_objs[0]) if lock_objs else None
        return {"action": "enter_code", "target": target, "code": code}
    if re.search(r"\b(use|unlock|insert|apply)\b", t) and items:
        return {
            "action": "use",
            "item": alias("item", items[0]),
            "target": alias("object", objs[0]) if objs else None,
        }
    if re.search(r"\b(take|grab|pick|collect|get)\b", t) and (items or objs):
        if items:
            return {"action": "take", "target": alias("item", items[0])}
        return {"action": "take", "target": alias("object", objs[0])}
    if re.search(r"\b(search|behind|lift|move|under|inside)\b", t) and objs:
        return {"action": "search", "target": alias("object", objs[0])}
    if re.search(r"\b(try|open|unlock)\b", t) and lock_objs:
        return {"action": "enter_code", "target": alias("object", lock_objs[0]), "code": None}
    if re.search(r"\b(examine|look|inspect|read|check|study|view|see|describe)\b", t):
        if items:
            return {"action": "examine", "target": alias("item", items[0])}
        if objs:
            return {"action": "examine", "target": alias("object", objs[0])}
    return {"action": "unknown"}
