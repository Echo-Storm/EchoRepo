import json
import sys
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_PATH = Path(xbmcvfs.translatePath(ADDON.getAddonInfo("path")))
sys.path.insert(0, str(ADDON_PATH / "lib"))
import profile_builder as pb  # noqa: E402

HEADING = "Echo Profiles"
USERDATA = Path(xbmcvfs.translatePath("special://profile"))
PROFILES = pb.load_profiles(ADDON_PATH / "lib" / "profiles.json")
DEVICE_KEYS = ("audiooutput.audiodevice", "audiooutput.passthroughdevice")
# Kodi's JSON-RPC has no per-setting details call: GetSettings returns a whole category, so the ones we touch are looked up there.
CATEGORIES = {"audiooutput.": ("system", "audio")}


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[script.echo.profiles] " + msg, level)


def rpc(method, **params):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    if reply.get("error"):
        log("%s %s -> %s" % (method, params, reply["error"]), xbmc.LOGERROR)
    return reply.get("result"), reply.get("error")


def current():
    try:
        return json.loads((USERDATA / pb.MARKER).read_text(encoding="utf-8")).get("profile")
    except (OSError, ValueError):
        return None


def category_details(key, cache):
    for prefix, (section, category) in CATEGORIES.items():
        if key.startswith(prefix):
            if prefix not in cache:
                res, _err = rpc("Settings.GetSettings", level="expert", filter={"section": section, "category": category})
                cache[prefix] = {s.get("id"): s for s in (res or {}).get("settings", [])}
            return cache[prefix].get(key)
    return None


def typed_like(value, example):
    """The profile stores every value as text; JSON-RPC wants the setting's own type (the type of its current value)."""
    if isinstance(example, bool):
        return value == "true"
    if isinstance(example, int):
        return int(value)
    return value


def apply_gui(name):
    """Kodi's own settings go through JSON-RPC: Kodi holds them in memory and would overwrite an edited guisettings.xml on exit."""
    done, skipped, cache = 0, [], {}
    for kind, _addon, key, value in pb.targets(PROFILES, name):
        if kind != "gui":
            continue
        if value is None:
            _res, err = rpc("Settings.ResetSettingValue", setting=key)
            if err:
                skipped.append(f"{key}: reset failed")
            else:
                done += 1
            continue
        if key in DEVICE_KEYS:
            info = category_details(key, cache)
            have = [o.get("value") for o in (info or {}).get("options", [])]
            if have and value not in have:
                skipped.append(f"{key}: no '{value.split('|')[-1]}' on this device, left as is")
                log("skip %s: %r not among %s" % (key, value, have))
                continue
        res, err = rpc("Settings.GetSettingValue", setting=key)
        if err:
            skipped.append(f"{key}: unknown to this Kodi")
            continue
        typed = typed_like(value, (res or {}).get("value"))
        _res, err = rpc("Settings.SetSettingValue", setting=key, value=typed)
        if err:
            skipped.append(f"{key}: refused")
            continue
        back, _err = rpc("Settings.GetSettingValue", setting=key)
        if (back or {}).get("value") != typed:
            skipped.append(f"{key}: Kodi kept {(back or {}).get('value')!r}")
            log("%s: set %r, Kodi now holds %r" % (key, typed, (back or {}).get("value")))
            continue
        done += 1
    return done, skipped


def main():
    names = list(PROFILES)
    now = current()
    items = [xbmcgui.ListItem(("[B]%s[/B]  (current)" if n == now else "%s") % n, PROFILES[n]["describe"]) for n in names]
    pick = xbmcgui.Dialog().select(HEADING, items, useDetails=True)
    if pick < 0:
        return
    name = names[pick]
    if not xbmcgui.Dialog().yesno(HEADING, "Apply [B]%s[/B] to this install?\n\n%s" % (name, PROFILES[name]["describe"])):
        return
    log("applying %s" % name)
    gui_done, skipped = apply_gui(name)
    try:
        changes = pb.apply(USERDATA, PROFILES, name, check_running=False, skip_kinds=("gui",))
    except Exception as exc:  # shown to the user and logged
        log("add-on settings failed: %r" % exc, xbmc.LOGERROR)
        xbmcgui.Dialog().ok(HEADING, "Add-on settings could not be applied:\n%s" % exc)
        return
    addon_done = len([c for c in changes if "pending" not in c and c["kind"] != "gui"])
    pending = [c for c in changes if "pending" in c]
    log("%s: kodi settings %d, add-on settings %d, pending %s, skipped %s" % (name, gui_done, addon_done, [c["addon"] + ":" + c["key"] for c in pending], skipped))
    lines = ["[B]%s[/B] applied." % name, "Kodi settings set: %d.  Add-on settings changed: %d." % (gui_done, addon_done)]
    if pending:
        lines.append("Not yet possible (run the add-on once first): %s." % ", ".join(sorted({c["addon"] for c in pending})))
    if skipped:
        lines.append("Skipped: " + "; ".join(skipped))
    lines.append("Restart Kodi now so every add-on re-reads its settings?")
    if xbmcgui.Dialog().yesno(HEADING, "\n".join(lines), yeslabel="Restart", nolabel="Later"):
        xbmc.executebuiltin("Quit")


if __name__ == "__main__":
    main()
