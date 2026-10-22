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


def rpc(method, **params):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    return reply.get("result"), reply.get("error")


def current():
    try:
        return json.loads((USERDATA / pb.MARKER).read_text(encoding="utf-8")).get("profile")
    except (OSError, ValueError):
        return None


def apply_gui(name):
    """Kodi's own settings go through JSON-RPC: Kodi holds them in memory and would overwrite an edited guisettings.xml on exit."""
    done, skipped = 0, []
    for kind, _addon, key, value in pb.targets(PROFILES, name):
        if kind != "gui":
            continue
        if value is None:
            _res, err = rpc("Settings.ResetSettingValue", setting=key)
            if err:
                skipped.append(f"{key}: {err.get('message', 'reset failed')}")
            else:
                done += 1
            continue
        if key in DEVICE_KEYS:
            res, _err = rpc("Settings.GetSettingOptions", setting=key)
            have = [o.get("value") for o in (res or {}).get("options", [])]
            if value not in have:
                skipped.append(f"{key}: no '{value.split('|')[-1]}' on this device, left as is")
                continue
        details, _err = rpc("Settings.GetSettingDetails", setting=key)
        kind_of = ((details or {}).get("setting") or {}).get("type")
        if kind_of == "boolean":
            typed = value == "true"
        elif kind_of == "integer":
            typed = int(value)
        else:
            typed = value
        _res, err = rpc("Settings.SetSettingValue", setting=key, value=typed)
        if err:
            skipped.append(f"{key}: {err.get('message', 'refused')}")
        else:
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
    gui_done, skipped = apply_gui(name)
    changes = pb.apply(USERDATA, PROFILES, name, check_running=False, skip_kinds=("gui",))
    addon_done = len([c for c in changes if "pending" not in c and c["kind"] != "gui"])
    pending = [c for c in changes if "pending" in c]
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
