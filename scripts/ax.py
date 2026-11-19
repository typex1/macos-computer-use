#!/usr/bin/env python
"""ax.py - macOS Accessibility (AXUIElement) layer: the native-app equivalent of a
DOM snapshot. Lists UI elements with role, title, value, state and exact screen
frame, finds elements by text, and acts on them without screenshots.

Usage:
  ax.py apps                                 running GUI apps (name, pid)
  ax.py tree  --app NAME [--depth N] [--all] UI tree of the app's windows (default depth 12,
                                             groups without text are folded unless --all)
  ax.py find  --app NAME TEXT [--role ROLE] [--exact]
                                             elements whose title/value/desc contain (or equal) TEXT
  ax.py click --app NAME TEXT [--role ROLE] [--nth K]
                                             press the element (AXPress), else click its centre
  ax.py menubar                              all status-bar (menu extra) items of all apps
  ax.py menubar-click TEXT                   click the menu extra whose title/desc matches TEXT
  ax.py focused                              the focused app, window and element

Frames are absolute screen points; use `cu.py --screen click X Y` for a raw click.
Flash/canvas content is opaque to AX; use cu.py screenshots / ocr.py there.
"""
import argparse
import re
import subprocess
import sys
import time

import ApplicationServices as AS
import Quartz
from AppKit import NSWorkspace

TEXT_ATTRS = ("AXTitle", "AXValue", "AXDescription", "AXHelp", "AXPlaceholderValue",
              "AXRoleDescription")
SKIP_ROLES_FOR_FOLD = {"AXGroup", "AXUnknown", "AXLayoutArea", "AXLayoutItem",
                       "AXSplitGroup", "AXScrollArea", "AXList"}


# ------------------------------------------------------------- low level

def attr(el, name):
    err, val = AS.AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def frame(el):
    pos, size = attr(el, "AXPosition"), attr(el, "AXSize")
    if pos is None or size is None:
        return None
    ok, p = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
    ok2, s = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    if not (ok and ok2):
        return None
    return int(p.x), int(p.y), int(s.width), int(s.height)


def text_of(el):
    parts = []
    for a in TEXT_ATTRS[:-1]:
        v = attr(el, a)
        if isinstance(v, str) and v.strip() and v not in parts:
            parts.append(v.strip())
        elif isinstance(v, (int, float, bool)) and a == "AXValue":
            parts.append(str(v))
    return " | ".join(parts)


def children(el):
    return attr(el, "AXChildren") or []


def state(el):
    bits = []
    if attr(el, "AXEnabled") is False:
        bits.append("disabled")
    if attr(el, "AXFocused"):
        bits.append("focused")
    if attr(el, "AXSelected"):
        bits.append("selected")
    v = attr(el, "AXValue")
    role = attr(el, "AXRole")
    if role in ("AXCheckBox", "AXRadioButton") and isinstance(v, int):
        bits.append("checked" if v else "unchecked")
    return " ".join(bits)


def pid_of(app_name):
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if a.localizedName() and a.localizedName().lower() == app_name.lower():
            return a.processIdentifier()
    out = subprocess.run(["pgrep", "-ix", app_name], capture_output=True, text=True).stdout.split()
    if out:
        return int(out[0])
    sys.exit(f"no running app named {app_name!r} (see `ax.py apps`)")


def app_element(app_name):
    el = AS.AXUIElementCreateApplication(pid_of(app_name))
    # Electron/Chromium apps (Slack, Teams, VS Code) build their AX tree lazily;
    # these attributes ask them to. Harmless for native apps.
    for a in ("AXManualAccessibility", "AXEnhancedUserInterface"):
        AS.AXUIElementSetAttributeValue(el, a, True)
    if not attr(el, "AXWindows"):
        time.sleep(0.5)
    return el


# ---------------------------------------------------------------- walking

def walk(el, depth, max_depth, visit, path="", shown=0):
    """depth = real depth (for the limit), shown = depth counting only printed nodes."""
    if depth > max_depth:
        return
    printed = visit(el, shown, path)
    for i, c in enumerate(children(el)):
        walk(c, depth + 1, max_depth, visit, f"{path}/{i}", shown + (1 if printed else 0))


def fmt(el, depth, show_all):
    role = attr(el, "AXRole") or "?"
    txt = text_of(el)
    fr = frame(el)
    st = state(el)
    if not show_all and role in SKIP_ROLES_FOR_FOLD and not txt:
        return None
    frs = f"@({fr[0]},{fr[1]} {fr[2]}x{fr[3]})" if fr else ""
    return f"{'  ' * depth}{role[2:]} {txt!r} {st} {frs}".rstrip()


def tree(app_name, max_depth, show_all):
    app = app_element(app_name)
    roots = list(attr(app, "AXWindows") or [])
    extras = attr(app, "AXExtrasMenuBar")
    if extras:
        roots.append(extras)
    if not roots:
        print(f"{app_name}: no windows exposed via AX")
    for r in roots:
        def visit(el, depth, path):
            line = fmt(el, depth, show_all)
            if line:
                print(line)
            return bool(line)
        walk(r, 0, max_depth, visit)


def find(app_name, text, role=None, max_depth=80, exact=False):
    app = app_element(app_name)
    pat = re.compile(r"^(?:" + re.escape(text) + r")(?:\s*\|.*)?$" if exact else re.escape(text), re.I)
    hits = []
    roots = list(attr(app, "AXWindows") or [])
    extras = attr(app, "AXExtrasMenuBar")
    if extras:
        roots.append(extras)

    def visit(el, depth, path):
        r = attr(el, "AXRole") or ""
        if role and r.lower() != role.lower() and r.lower() != "ax" + role.lower():
            return
        t = text_of(el)
        if t and pat.search(t):
            hits.append((el, r, t, frame(el), state(el)))
    for root in roots:
        walk(root, 0, max_depth, visit)
    return hits


def press(el):
    err, actions = AS.AXUIElementCopyActionNames(el, None)
    if actions and "AXPress" in actions:
        AS.AXUIElementPerformAction(el, "AXPress")
        return "AXPress"
    fr = frame(el)
    if not fr:
        sys.exit("element has no frame and no AXPress action")
    x, y = fr[0] + fr[2] / 2, fr[1] + fr[3] / 2
    for kind in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        ev = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.05)
    return f"click@({int(x)},{int(y)})"


def print_hits(hits):
    for i, (el, r, t, fr, st) in enumerate(hits):
        frs = f"@({fr[0]},{fr[1]} {fr[2]}x{fr[3]})" if fr else ""
        print(f"[{i}] {r[2:]} {t!r} {st} {frs}".rstrip())


# ---------------------------------------------------------------- menubar

def menubar_items():
    items = []
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        app = AS.AXUIElementCreateApplication(a.processIdentifier())
        extras = attr(app, "AXExtrasMenuBar")
        if not extras:
            continue
        for el in children(extras):
            items.append((a.localizedName(), el, attr(el, "AXRole") or "", text_of(el), frame(el)))
    # system status items (control centre etc.) live in SystemUIServer / ControlCenter apps
    items.sort(key=lambda it: it[4][0] if it[4] else 0)
    return items


def focused():
    front = NSWorkspace.sharedWorkspace().frontmostApplication()
    app = AS.AXUIElementCreateApplication(front.processIdentifier())
    el = attr(app, "AXFocusedUIElement")
    print("app:", front.localizedName(), front.processIdentifier())
    win = attr(app, "AXFocusedWindow")
    print("window:", attr(win, "AXTitle") if win else None, frame(win) if win else "")
    if el:
        print("element:", attr(el, "AXRole"), repr(text_of(el)), frame(el))


# ------------------------------------------------------------------- main

def main():
    if not AS.AXIsProcessTrusted():
        sys.exit("Accessibility permission missing for this process (System Settings > Privacy & Security > Accessibility)")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("apps")
    s = sub.add_parser("tree"); s.add_argument("--depth", type=int, default=80); s.add_argument("--all", action="store_true")
    s = sub.add_parser("find"); s.add_argument("text"); s.add_argument("--role"); s.add_argument("--exact", action="store_true", help="title must equal TEXT (description after ' | ' ignored)")
    s = sub.add_parser("click"); s.add_argument("text"); s.add_argument("--role"); s.add_argument("--nth", type=int, default=0); s.add_argument("--exact", action="store_true")
    sub.add_parser("menubar")
    s = sub.add_parser("menubar-click"); s.add_argument("text")
    sub.add_parser("focused")
    a = p.parse_args()

    if a.cmd == "apps":
        for ap in NSWorkspace.sharedWorkspace().runningApplications():
            if ap.activationPolicy() == 0:  # regular GUI apps
                print(f"{ap.processIdentifier():>6}  {ap.localizedName()}")
    elif a.cmd == "focused":
        focused()
    elif a.cmd == "menubar":
        for owner, el, role, txt, fr in menubar_items():
            frs = f"@({fr[0]},{fr[1]} {fr[2]}x{fr[3]})" if fr else ""
            print(f"{owner:<22} {role[2:]:<12} {txt!r} {frs}")
    elif a.cmd == "menubar-click":
        pat = re.compile(re.escape(a.text), re.I)
        hits = [(o, el, t) for o, el, r, t, fr in menubar_items() if pat.search(t or "") or pat.search(o or "")]
        if not hits:
            sys.exit("no menu extra matches")
        o, el, t = hits[0]
        print(f"{o}: {t!r} -> {press(el)}")
    else:
        if not a.app:
            sys.exit("--app NAME required")
        if a.cmd == "tree":
            tree(a.app, a.depth, a.all)
        elif a.cmd == "find":
            print_hits(find(a.app, a.text, a.role, exact=a.exact))
        elif a.cmd == "click":
            hits = find(a.app, a.text, a.role, exact=a.exact)
            if not hits:
                sys.exit(f"no element matching {a.text!r}")
            if a.nth >= len(hits):
                print_hits(hits); sys.exit(f"--nth {a.nth} out of range")
            subprocess.run(["osascript", "-e", f'tell application "{a.app}" to activate'], check=False)
            time.sleep(0.2)
            el, r, t, fr, st = hits[a.nth]
            print(f"{r[2:]} {t!r} -> {press(el)}")


if __name__ == "__main__":
    main()
