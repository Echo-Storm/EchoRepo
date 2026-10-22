#!/usr/bin/env python3
"""Apply one of the owner's config sets (data/profiles.json) to a Kodi userdata folder.

usage:
  profile_builder.py list
  profile_builder.py status [--userdata DIR]            which profile does this userdata match, and what differs
  profile_builder.py apply NAME [--userdata DIR] [--dry-run]

A profile is a small list of settings (Kodi's guisettings.xml, add-on settings.xml files, Gears' settings.db). Every setting that any
profile sets is 'managed': a profile that does not set it puts it back to the default, so changing from one profile to another is
repeatable. Kodi must be closed (it rewrites settings files when it quits). Every file that changes is copied first to
<userdata>/profile_backups/<time>/. Nothing here handles secrets (tokens, passwords): that is the credentials tool (K31).
Default userdata: %APPDATA%/Kodi/userdata."""
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "data" / "profiles.json"
MARKER = "profile_builder.json"
GEARS_DB = "databases/settings.db"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'


class Refused(Exception):
    pass


def load_profiles(path=PROFILES):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    def sub(value):
        if isinstance(value, str) and value.startswith("@"):
            return data[value[1:]]
        if isinstance(value, list):
            return [sub(v) for v in value]
        return value

    profiles = {}
    for name, p in data["profiles"].items():
        profiles[name] = {
            "describe": p.get("describe", ""),
            "gui": {k: sub(v) for k, v in p.get("gui", {}).items()},
            "addons": {a: {store: {k: sub(v) for k, v in keys.items()} for store, keys in stores.items()}
                       for a, stores in p.get("addons", {}).items()},
        }
    return profiles


def managed_keys(profiles):
    """{('gui', None): set(keys), ('xml', addon): set(keys), ('db', addon): set(keys)} over every profile."""
    out = {}
    for p in profiles.values():
        out.setdefault(("gui", None), set()).update(p["gui"])
        for addon, stores in p["addons"].items():
            for store, keys in stores.items():
                out.setdefault((store, addon), set()).update(keys)
    return out


def targets(profiles, name):
    """Every managed setting with the value this profile wants: [(kind, addon, key, value|list|None)]."""
    want = profiles[name]
    result = []
    for (kind, addon), keys in sorted(managed_keys(profiles).items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        for key in sorted(keys):
            if kind == "gui":
                value = want["gui"].get(key)
            else:
                value = want["addons"].get(addon, {}).get(kind, {}).get(key)
            result.append((kind, addon, key, value))
    return result


def kodi_running():
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq kodi.exe", "/NH"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "kodi.exe" in out.lower()


# ---- XML settings (guisettings.xml and add-on settings.xml)

def read_xml(path):
    if not path.exists():
        return None
    return ET.parse(path)


def xml_get(tree, key):
    """(value, is_default) of a setting; (None, True) when absent."""
    if tree is not None:
        for el in tree.getroot().iter("setting"):
            if el.get("id") == key:
                return (el.text or ""), el.get("default") == "true"
    return None, True


def xml_set(tree, key, value):
    root = tree.getroot()
    for el in root.iter("setting"):
        if el.get("id") == key:
            el.attrib.pop("default", None)
            el.text = value
            return
    ET.SubElement(root, "setting", {"id": key}).text = value


def xml_reset(tree, key):
    root = tree.getroot()
    for parent in root.iter():
        for el in list(parent):
            if el.tag == "setting" and el.get("id") == key:
                parent.remove(el)


def write_xml(tree, path):
    ET.indent(tree, space="    ")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ET.tostring(tree.getroot(), encoding="unicode")
    path.write_text(XML_HEAD + body, encoding="utf-8", newline="\n")


def new_xml():
    return ET.ElementTree(ET.Element("settings", {"version": "2"}))


def declared_default(userdata, addon, key):
    """The default the add-on itself declares for a setting (old-style default="x" or new-style <default>x</default>), or None."""
    if not addon:
        return None
    path = Path(userdata).parent / "addons" / addon / "resources" / "settings.xml"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'<setting\s(?:[^>]*\s)?id="%s"[^>]*>' % re.escape(key), text)
    if not m:
        return None
    attr = re.search(r'\sdefault="([^"]*)"', m.group(0))
    if attr:
        return attr.group(1)
    block = text[m.end():m.end() + 400]
    new = re.search(r"<default>([^<]*)</default>", block)
    return new.group(1) if new else None


# ---- Gears settings.db: settings(setting_id, setting_type, setting_default, setting_value); an option setting has a '<id>_name' row too

def db_get(con, key):
    row = con.execute("SELECT setting_value, setting_default FROM settings WHERE setting_id=?", (key,)).fetchone()
    return row


def db_expected(con, key, value):
    """What the rows must hold: (value, name|None). A reset takes the row's own default."""
    row = db_get(con, key)
    if row is None:
        return None
    if value is None:
        name_row = db_get(con, key + "_name")
        return row[1], (name_row[1] if name_row else None)
    if isinstance(value, list):
        return value[0], value[1]
    return value, None


# ---- plan / apply

def plan(userdata, profiles, name):
    """List of changes still needed: dicts with kind, addon, key, current, want, note."""
    userdata = Path(userdata)
    changes = []
    trees, dbs = {}, {}
    try:
        _plan_into(changes, userdata, profiles, name, trees, dbs)
    finally:
        for con in dbs.values():
            con.close()
    return changes


def _plan_into(changes, userdata, profiles, name, trees, dbs):
    for kind, addon, key, value in targets(profiles, name):
        if kind in ("gui", "xml"):
            path = userdata / "guisettings.xml" if kind == "gui" else userdata / "addon_data" / addon / "settings.xml"
            if path not in trees:
                trees[path] = read_xml(path)
            cur, is_default = xml_get(trees[path], key)
            if value is None:
                if cur is not None and not is_default and cur != declared_default(userdata, addon, key):
                    changes.append(dict(kind=kind, addon=addon, key=key, current=cur, want=None, path=path))
            elif cur != value:   # equal to what is wanted, even if Kodi marks it default: nothing to do
                changes.append(dict(kind=kind, addon=addon, key=key, current=cur, want=value, path=path))
        else:
            path = userdata / "addon_data" / addon / GEARS_DB
            if not path.exists():
                changes.append(dict(kind=kind, addon=addon, key=key, current=None, want=value, path=path, pending="database not created yet: run the add-on once"))
                continue
            if path not in dbs:
                dbs[path] = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            con = dbs[path]
            exp = db_expected(con, key, value)
            if exp is None:
                changes.append(dict(kind=kind, addon=addon, key=key, current=None, want=value, path=path, pending="setting not in the database yet"))
                continue
            want_value, want_name = exp
            cur = db_get(con, key)[0]
            cur_name = (db_get(con, key + "_name") or [None])[0]
            if cur != want_value or (want_name is not None and cur_name != want_name):
                changes.append(dict(kind=kind, addon=addon, key=key, current=cur, want=value, path=path, db_value=want_value, db_name=want_name))


def apply(userdata, profiles, name, dry_run=False, check_running=True, skip_kinds=()):
    userdata = Path(userdata)
    if name not in profiles:
        raise Refused(f"unknown profile {name!r}; known: {', '.join(profiles)}")
    if not userdata.is_dir():
        raise Refused(f"no such folder: {userdata}")
    if check_running and not dry_run and kodi_running():
        raise Refused("Kodi is running: close it first (it rewrites the settings files when it quits)")
    changes = plan(userdata, profiles, name)
    real = [c for c in changes if "pending" not in c and c["kind"] not in skip_kinds]
    pending = [c for c in changes if "pending" in c]
    if dry_run:
        return changes
    by_file = {}
    for c in real:
        by_file.setdefault(c["path"], []).append(c)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for path, items in by_file.items():
        if path.exists():
            dest = userdata / "profile_backups" / stamp / path.relative_to(userdata)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        if items[0]["kind"] == "db":
            con = sqlite3.connect(path)
            with con:
                for c in items:
                    con.execute("UPDATE settings SET setting_value=? WHERE setting_id=?", (c["db_value"], c["key"]))
                    if c["db_name"] is not None:
                        con.execute("UPDATE settings SET setting_value=? WHERE setting_id=?", (c["db_name"], c["key"] + "_name"))
            con.close()
        else:
            tree = read_xml(path) or new_xml()
            for c in items:
                if c["want"] is None:
                    xml_reset(tree, c["key"])
                else:
                    xml_set(tree, c["key"], c["want"])
            write_xml(tree, path)
    marker = userdata / MARKER
    marker.write_text(json.dumps({"profile": name, "applied": stamp, "pending": [f"{c['addon']}:{c['key']}" for c in pending]}, indent=1), encoding="utf-8")
    return changes


def status(userdata, profiles):
    """{profile: number of settings that differ}."""
    return {name: len(plan(userdata, profiles, name)) for name in profiles}


def default_userdata():
    appdata = os.environ.get("APPDATA")
    return Path(appdata) / "Kodi" / "userdata" if appdata else Path.home() / ".kodi" / "userdata"


def show(c):
    who = c["addon"] or "guisettings"
    want = "(default)" if c["want"] is None else (c["want"] if not isinstance(c["want"], list) else c["want"][0] + " " + c["want"][1])
    note = f"   [{c['pending']}]" if "pending" in c else ""
    return f"  {who:32} {c['key']:34} {str(c['current'])!s:24} -> {want}{note}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["list", "status", "apply"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--userdata")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    profiles = load_profiles()
    userdata = Path(args.userdata) if args.userdata else default_userdata()
    if args.command == "list":
        for n, p in profiles.items():
            print(f"{n}: {p['describe']}")
        return 0
    if args.command == "status":
        marker = userdata / MARKER
        print("last applied:", json.loads(marker.read_text(encoding="utf-8"))["profile"] if marker.exists() else "(never)")
        for n, diff in status(userdata, profiles).items():
            print(f"  {n:14} {'matches' if diff == 0 else str(diff) + ' setting(s) differ'}")
        return 0
    if not args.name:
        ap.error("apply needs a profile name")
    try:
        changes = apply(userdata, profiles, args.name, dry_run=args.dry_run)
    except Refused as e:
        print("refused:", e)
        return 2
    print(("would change" if args.dry_run else "changed"), len([c for c in changes if 'pending' not in c]), "setting(s) in", userdata)
    for c in changes:
        print(show(c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
