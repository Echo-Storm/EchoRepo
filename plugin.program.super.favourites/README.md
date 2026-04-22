# Super Favourites — v2.4.0

**Addon ID:** `plugin.program.super.favourites`  
**Authors:** Sean Poyser (seanpoyser@gmail.com), John Moore (jmooremcc@hotmail.com)  
**Maintainer (v2.4.0 patch):** Echo / xechostormx  
**License:** GNU General Public License v2  
**Minimum Kodi version:** 19 (Matrix) — Python 3 required  
**Forum:** http://forum.xbmc.org/showthread.php?tid=192662  
**Source:** https://github.com/jmooremcc/plugin.program.super.favourites

---

## What It Does

Super Favourites is a Kodi addon that lets you pin items from any other addon — radio stations, video plugins, music sources, anything — into a single organized menu. You can create subfolders, reorder items, rename them, and launch them without digging through the source addon each time.

The core data format is a standard Kodi `favourites.xml` file. Your favourites are stored in:

```
special://profile/addon_data/plugin.program.super.favourites/Super Favourites/
```

Each subfolder you create is its own directory containing its own `favourites.xml`. This means the data is portable, human-readable, and not locked into any proprietary format.

---

## Installation

Install from zip via **Kodi → Add-ons → Install from zip file**.

The zip must contain a single root folder named exactly `plugin.program.super.favourites`. This zip is structured correctly for a drop-in install or upgrade.

**Upgrading from 2.3.7:** Your existing favourites data is not touched. The addon data directory is separate from the addon itself. No reconfiguration is needed after upgrade.

---

## How to Add Items

There are two ways to add an item to Super Favourites:

**Method 1 — Right-click context menu (recommended)**

Navigate to the item you want to pin in any addon. Right-click (or long-press, or press C on keyboard). If the SF context menu is enabled in settings, you will see **"Add to Super Favourites"**. Select it, choose a destination folder, optionally rename the item, and it is saved.

**Method 2 — From within Super Favourites**

Open Super Favourites, navigate to the folder you want to add to, and use the **"New Super Favourite"** item at the bottom of the list.

---

## Favourites XML Format

Each `favourites.xml` file follows Kodi's standard favourites format:

```xml
<favourites>
    <favourite name="SHOUTcast" thumb="special://home/addons/plugin.audio.shoutcast/icon.png">
        ActivateWindow(10025,"plugin://plugin.audio.shoutcast?sf_options=...",return)
    </favourite>
</favourites>
```

The `sf_options=...` query parameter is Super Favourites' internal metadata blob. It stores fanart path, description, and other display info. It is URL-encoded and appended to the plugin URL. It is stripped before the command is executed so the target addon never sees it.

You can hand-edit these files safely. The only things to be careful about:

- `name` and `thumb` attributes must be properly XML-escaped (the addon handles this on write)
- The command inside the element must be a valid Kodi builtin: `ActivateWindow(...)`, `PlayMedia(...)`, `RunScript(...)`, etc.
- Do not duplicate entries — SF uses the command string (minus sf_options) as the identity key

---

## Skin Integration (chooser.py)

Super Favourites exposes `chooser.py` for skin developers who want to let users pick a SF item via a browse dialog and bind the result to a skin property.

**Usage:**

```
RunScript(special://home/addons/plugin.program.super.favourites/chooser.py,
          property=CustomSuperFavourite1
          &path=Folder 1/Folder 2
          &changetitle=true)
```

**Parameters:**

| Parameter | Required | Description |
|---|---|---|
| `property` | Yes | Name of the skin property to set on selection |
| `path` | No | Starting subfolder path (relative to SF root). Defaults to root. |
| `changetitle` | No | If `true`, prompts user to rename the item after selecting. Defaults to `false`. |

**Properties set after selection:**

```
CustomSuperFavourite1.Path     — fully formed Kodi action command
CustomSuperFavourite1.Label    — display name of the item
CustomSuperFavourite1.Icon     — path to thumbnail image
CustomSuperFavourite1.IsFolder — 'true' if the item is a SF subfolder
```

**Launching via skin:**

To open Super Favourites starting in a specific folder bound to a skin property:

```
ActivateWindow(10025,"plugin://plugin.program.super.favourites/?folder=CustomSuperFavourite1")
```

**Using as a widget:**

To populate a list/widget in a skin from a SF folder (suppresses internal navigation items):

```xml
<content target="video">
    plugin://plugin.program.super.favourites/?content=CustomSuperFavourite1
    &reload=$INFO[Window(Home).Property(Super_Favourites_Count)]
</content>
```

The `reload` parameter causes the widget to refresh automatically when the SF folder contents change.

---

## Settings Reference

Settings are accessed via **Kodi → Add-ons → Super Favourites → Configure** or from the SF context menu.

### Context Menu

| Setting | Description |
|---|---|
| Enable SF context menu | Activates the right-click intercept. When off, right-click passes through to Kodi's standard menu. |
| Show "Add to SF" on standard menu | Adds an "Add to Super Favourites" entry directly to Kodi's built-in context menu (separate from the SF menu). |
| Show "Addon settings" | Includes an option to open the source addon's settings from the SF context menu. |
| Show "SF settings" | Includes a shortcut to SF settings from the context menu. |
| Show "Standard menu" | Adds a fallback to Kodi's native context menu at the bottom of the SF menu. |
| Context menu style | Dialog box vs. overlay panel. |
| Whitelist | Addons where right-click passes through to the standard Kodi menu instead of SF. |

### Folders and Display

| Setting | Description |
|---|---|
| Data folder | Where SF stores its favourites. Defaults to `special://profile/addon_data/plugin.program.super.favourites/`. Changing this does not migrate existing data. |
| Show Kodi favourites | Whether to show your Kodi favourites folder inside SF. |
| Inherit folder icon | If enabled, a folder's icon is inherited from its first item. |
| Alphabetical sort | Sort items alphabetically within folders. |
| Numeric labels | Prefix item labels with sequential numbers. |

### Hotkey

SF can be assigned a hotkey to open it from anywhere in Kodi. Set via the Hotkey setting. Writes a keymap file to `special://profile/keymaps/super_favourites_hot.xml`.

### Import / Export

SF can export your entire favourites tree as a zip archive and import it back. Icons and fanart are included in the export if they are local files. Useful for backup or migrating to a new device.

---

## Changes in v2.4.0

This release is a bug-fix and cleanup patch against the upstream v2.3.7 release. No new features were added. No favourites data format was changed. Existing installations upgrade cleanly.

### Bug Fixes

**`utils.py` — `getKodiSetting()` always returned None (silent crash)**

The function used `dict.has_key()` which was removed in Python 3. On any Kodi 19+ installation this threw `AttributeError` silently inside a bare `except` block, causing the function to always return `None`. Any feature that read Kodi settings via JSON-RPC (skin changer, etc.) was silently broken. Fixed by replacing `has_key()` with the standard `in` operator.

**`favourite.py` — "FLLY FORMED" dialog appearing randomly**

The `isKodiCommand()` function contained `utils.DialogOK("FLLY FORMED")` — a developer debug popup that was never removed before release. This caused a random dialog box to appear mid-session. The line has been removed. The function's actual logic is unchanged.

**`download.py` — Confirm/Cancel buttons were swapped**

The download confirmation dialog used positional arguments in the wrong order, and then tested `== 1` (True/Yes) to cancel rather than to proceed. Clicking "Confirm" cancelled the download; clicking "Cancel" started it. Fixed using named `nolabel`/`yeslabel` arguments and corrected boolean logic.

**`favourite.py` — Unbounded recursion in reorder**

`_shiftUpIndex()` and `_shiftDownIndex()` are recursive functions used when reordering items. If a favourites file contained only invalid items (dead addon links, missing plugins), these functions would recurse indefinitely until Python hit its stack limit and threw `RecursionError`. Fixed by adding a `depth` parameter that caps recursion at the list length and returns the original index if no valid item is found.

**`yt.py` — Module crashed on import (Python 3)**

Nine calls to `dict.has_key()` throughout `yt.py` caused `AttributeError` on import under Python 3. The YouTube API this module targets has been defunct since approximately 2014, but the module is still imported in `default.py`, meaning the crash could surface. All `has_key()` calls replaced with `in`.

### Debug Artifact Removal

The following developer artifacts were removed that had no effect on functionality but produced unwanted side effects:

**`service.py` — `LCLDEBUG = True`**  
A hardcoded debug flag caused the service (which runs at every Kodi startup) to `print()` the state of all three context menu toggles to stdout on startup and on every settings change. Flag and all guarded `print()` blocks removed.

**`hot.py` — `print("HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH")`**  
Two debug `print()` statements were present at module level, executing every time the hotkey was pressed. Removed. The actual `xbmc.executebuiltin()` call that triggers the addon is unchanged.

**`timer.py`, `capture.py` — bare `print()` in exception handlers**  
Error paths fell back to `print()`, which is invisible in Kodi's log. Replaced with `xbmc.log(..., xbmc.LOGERROR)`.

### Python 3 Modernization

**Legacy version constants set to `False`**  
`utils.py` computed boolean flags for Kodi versions 12–17 (Frodo through Krypton) at runtime. These could never be `True` on any currently supported Kodi. All flags (`FRODO`, `GOTHAM`, `HELIX`, `ISENGARD`, `KRYPTON`) are now hardcoded to `False`. The `if FRODO:` branches throughout the codebase remain as dead-letter code but no longer evaluate.

**All `print()` calls replaced with `xbmc.log()`**  
Any remaining bare `print()` statements in non-test code have been replaced with properly leveled `xbmc.log()` calls so errors appear in the Kodi debug log.

### Context Menu Cleanup

The SF right-click menu previously offered up to ten options. For a plugin whose primary purpose is pinning items to a custom menu, most of these were unnecessary. The following were removed:

| Removed item | What it did |
|---|---|
| iSearch | Searched the currently highlighted item's label via a configured search addon |
| iSearch using [default] | Same but with a preset search target |
| iRecommend | Related content search |
| Copy item and metadata | Copied full media metadata (cast, plot, rating, etc.) to a clipboard buffer |
| View fullsize images | Opened the item's fanart and thumbnail in a viewer |
| Quick launch Super Favourites | Opened SF from within the context menu |
| Now playing | Jumped to the video playlist window |
| Download using Super Favourites | Downloaded the currently playing stream to disk |
| Plugin extension slots | A dynamic system allowing third-party `.py` scripts to inject additional menu entries |

Functions removed from `menuUtils.py` as a result: `getCast()`, `getMovieCast()`, `getTVShowCast()`, `getSeasonCast()`, `getEpisodeCast()`, `doDownload()`, `getDownloadTitle()`, `getExt()`. The cast lookup chain made JSON-RPC calls to Kodi's video library on every right-click regardless of whether cast data was relevant.

`getCurrentMeta()` was simplified: cast lookup removed, basic info labels (title, genre, description, etc.) retained for the add-to-favourites path.

**The SF context menu now shows only:**
1. Add to Super Favourites
2. Addon Settings *(settings for the addon the highlighted item belongs to)*
3. Super Favourites Settings
4. Standard context menu *(optional fallback to Kodi's built-in menu)*

Items 2–4 are each individually toggleable in SF settings. Item 1 is controlled by the "Enable SF context menu" master toggle.

---

## File Reference

| File | Purpose |
|---|---|
| `default.py` | Main plugin entry point. Handles all URL routing and list building. |
| `service.py` | Background service. Runs at startup to verify keymaps, set window properties for context menu visibility, and handle settings changes. |
| `capture.py` | Right-click context menu. Intercepts the context menu action and presents the SF menu. |
| `menu_addtofaves.py` | Standalone script registered in `addon.xml` as a Kodi context menu item for the "Add to SF" entry on the standard menu. |
| `menuUtils.py` | Shared utilities for the context menu: reads current list item params, builds the command string, writes to the favourites file. |
| `favourite.py` | Core favourites data layer. Reads, writes, searches, moves, and reorders items in `favourites.xml`. |
| `utils.py` | Shared constants and helpers used across the addon. |
| `player.py` | Playback dispatch. Decides how to execute a saved favourite (ActivateWindow, PlayMedia, RunPlugin, etc.). |
| `importer.py` | Import/export of the full favourites tree as a zip archive. |
| `chooser.py` | Browse dialog for skin integration. |
| `imagecache.py` | Copies local icons and fanart into the export archive and restores them on import. |
| `locking.py` | Folder lock/PIN feature. |
| `search.py` | SF's built-in search over saved favourites. |
| `globalsearch.py` | Integration shim for the GlobalSearch addon. |
| `history.py` | Recently played items tracking. |
| `cache.py` | Simple property-based cache. |
| `sfile.py` | Filesystem abstraction over `xbmcvfs` for path handling. |
| `parameters.py` | URL parameter parsing for the plugin's own URLs. |
| `yt.py` | Legacy YouTube handler from 2013. The YouTube API it targets is defunct. The module is imported in `default.py` but the code path it serves no longer functions. Retained to avoid breaking the import chain. |
| `hot.py` | Hotkey handler. Executed by the keymap when the assigned hotkey is pressed. |
| `timer.py` | Cache expiry utility, called as a script. |
| `download.py` | Stream download utility. Retained for import compatibility; download option removed from context menu. |
| `standardMenu.py` | Wrapper that re-invokes Kodi's native context menu. |
| `quicklaunch.py` | Quick-launch overlay for SF folders. |
| `whitelist.py` | Manages the addon whitelist for context menu passthrough. |
| `keyProgrammer.py` | UI for assigning the hotkey. |
| `menus.py` | Menu display helpers (dialog vs. overlay styles). |
| `selector.py` | Generic selection dialog used internally. |
| `viewer.py` | Fullsize image viewer. Retained but no longer accessible from context menu. |
| `imagebrowser.py` | Image browsing dialog for custom icons. |
| `clipboard.py` | Internal clipboard for copy/paste of item metadata between folders. |
| `playlist.py` | Playlist detection and playback. |
| `quicknet.py` | Quick-add for network/SMB paths. |
| `launcher.py` | External launcher integration. |

---

## Known Limitations

**`yt.py` is non-functional.** The YouTube Data API v2 that this module used was shut down in 2014. The module is Python 3 compatible as of this release (no more import crash) but playing YouTube content through it will fail. Use the official YouTube addon instead.

**Import/export of remote favourites** requires the remote location to be accessible and serve a zip file with the expected structure. No authentication is supported.

**The Plugins/ extension system** has been removed from the context menu in this release. If you have custom `.py` scripts in `addon_data/plugin.program.super.favourites/Plugins/`, they will no longer be called from the right-click menu. The directory itself is still created at startup.
