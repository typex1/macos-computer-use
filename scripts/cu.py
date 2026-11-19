#!/usr/bin/env python
"""cu.py - minimal "computer use" toolset for macOS.

All coordinates are LOGICAL POINTS relative to the top-left corner of the
target application's front window, matching what `screenshot` produces
(the capture is downscaled from Retina to 1x so pixel == point).

Usage:
  cu.py windows                         list on-screen windows
  cu.py screenshot USE-CASE [--grid N] [--full]
                                        capture target window to $CU_SHOTS_DIR/cu_<use-case>.png;
                                        long side is downscaled to 1200 px unless --full/--grid
  cu.py click X Y [--double] [--right]  click at window coords
  cu.py move X Y                        move pointer
  cu.py drag X1 Y1 X2 Y2                press, drag, release
  cu.py type TEXT                       type unicode text
  cu.py key COMBO                       e.g. "a", "return", "cmd+c", "shift+tab"
  cu.py scroll X Y DX DY                scroll wheel at position
  cu.py activate                        bring target app to front

Global options: --app NAME (default $CU_APP, else the frontmost app); --screen makes
click/move/drag coordinates absolute screen points (for menu bar, Dock, dialogs).
Env: CU_SHOTS_DIR (default ./.computer-use/screenshots), CU_KEEP (default 20 newest kept).
  cu.py screenshot NAME --region X,Y,W,H   capture a screen area (same coords as --screen)
"""
import argparse
import os
import re
import sys
import time

import Quartz
from Quartz import (
    CGEventCreateKeyboardEvent, CGEventCreateMouseEvent, CGEventCreateScrollWheelEvent,
    CGEventKeyboardSetUnicodeString, CGEventPost, CGEventSetFlags, CGEventSetIntegerValueField,
    CGWindowListCopyWindowInfo, CGWindowListCreateImage, kCGEventLeftMouseDown,
    kCGEventLeftMouseDragged, kCGEventLeftMouseUp, kCGEventMouseMoved, kCGEventRightMouseDown,
    kCGEventRightMouseUp, kCGHIDEventTap, kCGMouseButtonLeft, kCGMouseButtonRight,
    kCGMouseEventClickState, kCGNullWindowID, kCGScrollEventUnitLine,
    kCGWindowImageBoundsIgnoreFraming, kCGWindowListOptionIncludingWindow,
    kCGWindowListOptionOnScreenOnly,
)
from PIL import Image, ImageDraw

# Screenshots are ephemeral working memory. They go to $CU_SHOTS_DIR (default
# ./.computer-use/screenshots under the current working directory) and only the
# newest $CU_KEEP files (default 20) are kept; older ones are deleted on each
# capture. Durable knowledge belongs in app-notes/*.md as text, not as PNGs.
SHOTS_DIR = os.environ.get("CU_SHOTS_DIR") or os.path.join(os.getcwd(), ".computer-use", "screenshots")
KEEP = int(os.environ.get("CU_KEEP", "20"))


def shot_path(use_case):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", use_case.strip()).strip("-")
    if not slug:
        sys.exit("use-case name must contain letters or digits")
    os.makedirs(SHOTS_DIR, exist_ok=True)
    return os.path.join(SHOTS_DIR, f"cu_{slug}.png")


def prune_shots():
    if KEEP <= 0:
        return
    files = [os.path.join(SHOTS_DIR, f) for f in os.listdir(SHOTS_DIR) if f.endswith(".png")]
    files.sort(key=os.path.getmtime, reverse=True)
    for f in files[KEEP:]:
        try:
            os.remove(f)
        except OSError:
            pass


def frontmost_app():
    from AppKit import NSWorkspace
    a = NSWorkspace.sharedWorkspace().frontmostApplication()
    return a.localizedName() if a else None

# ---------------------------------------------------------------- windows

def list_windows():
    infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    out = []
    for w in infos:
        if w.get("kCGWindowLayer", 0) != 0:
            continue
        b = w["kCGWindowBounds"]
        out.append({
            "id": w["kCGWindowNumber"],
            "app": w.get("kCGWindowOwnerName", ""),
            "pid": w.get("kCGWindowOwnerPID"),
            "title": w.get("kCGWindowName", ""),
            "x": int(b["X"]), "y": int(b["Y"]), "w": int(b["Width"]), "h": int(b["Height"]),
        })
    return out


SCREEN = {"id": None, "app": "<screen>", "x": 0, "y": 0, "w": 0, "h": 0}


def find_window(app):
    if app == "<screen>":
        return SCREEN
    cands = [w for w in list_windows() if w["app"].lower() == app.lower() and w["w"] > 50]
    if not cands:
        sys.exit(f"no on-screen window for app '{app}'")
    return cands[0]


def to_screen(win, x, y):
    return win["x"] + x, win["y"] + y


def activate(app):
    if app == "<screen>":
        return
    import subprocess
    subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], check=False)
    time.sleep(0.3)

# ------------------------------------------------------------- screenshot

MAX_SIDE = 1200  # default downscale target for the long side; --full disables


def screenshot(app, use_case, grid, region=None, full=False):
    out = shot_path(use_case)
    if region:
        x, y, w, h = region
        win = {"id": None, "app": "<screen>", "x": x, "y": y, "w": w, "h": h}
        img_ref = CGWindowListCreateImage(
            Quartz.CGRectMake(x, y, w, h), kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID, 0)
    else:
        win = find_window(app)
        img_ref = CGWindowListCreateImage(
            Quartz.CGRectNull, kCGWindowListOptionIncludingWindow, win["id"],
            kCGWindowImageBoundsIgnoreFraming)
    if img_ref is None:
        sys.exit("capture failed (Screen Recording permission?)")
    w = Quartz.CGImageGetWidth(img_ref)
    h = Quartz.CGImageGetHeight(img_ref)
    bpr = Quartz.CGImageGetBytesPerRow(img_ref)
    data = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img_ref))
    img = Image.frombuffer("RGBA", (w, h), bytes(data), "raw", "BGRA", bpr, 1)
    # downscale to logical points so image coords == click coords
    img = img.resize((win["w"], win["h"]), Image.LANCZOS).convert("RGB")
    scale = 1.0
    if not full and not grid and max(win["w"], win["h"]) > MAX_SIDE:
        scale = MAX_SIDE / max(win["w"], win["h"])
        img = img.resize((round(win["w"] * scale), round(win["h"] * scale)), Image.LANCZOS)
    if grid:
        d = ImageDraw.Draw(img)
        for gx in range(0, win["w"], grid):
            d.line([(gx, 0), (gx, win["h"])], fill=(255, 0, 255), width=1)
            d.text((gx + 2, 2), str(gx), fill=(255, 0, 255))
        for gy in range(0, win["h"], grid):
            d.line([(0, gy), (win["w"], gy)], fill=(255, 0, 255), width=1)
            d.text((2, gy + 2), str(gy), fill=(255, 0, 255))
    img.save(out)
    prune_shots()
    note = "" if scale == 1.0 else f" image scaled x{scale:.3f}: multiply image coords by {1/scale:.2f} (or use ax.py/ocr.py for coords)"
    print(f"{out} {win['w']}x{win['h']} window@({win['x']},{win['y']}) app={win['app']!r}{note}")

# ----------------------------------------------------------------- mouse

def _mouse(kind, pt, button=kCGMouseButtonLeft, clicks=1):
    ev = CGEventCreateMouseEvent(None, kind, pt, button)
    CGEventSetIntegerValueField(ev, kCGMouseEventClickState, clicks)
    CGEventPost(kCGHIDEventTap, ev)


def move(app, x, y):
    win = find_window(app)
    _mouse(kCGEventMouseMoved, to_screen(win, x, y))


def click(app, x, y, double=False, right=False):
    activate(app)
    win = find_window(app)
    pt = to_screen(win, x, y)
    _mouse(kCGEventMouseMoved, pt)
    time.sleep(0.05)
    down, up, btn = ((kCGEventRightMouseDown, kCGEventRightMouseUp, kCGMouseButtonRight)
                     if right else (kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft))
    n = 2 if double else 1
    for i in range(1, n + 1):
        _mouse(down, pt, btn, i); time.sleep(0.04)
        _mouse(up, pt, btn, i); time.sleep(0.06)
    print(f"clicked ({x},{y}) -> screen {pt}")


def drag(app, x1, y1, x2, y2, steps=15):
    activate(app)
    win = find_window(app)
    p1, p2 = to_screen(win, x1, y1), to_screen(win, x2, y2)
    _mouse(kCGEventMouseMoved, p1); time.sleep(0.05)
    _mouse(kCGEventLeftMouseDown, p1); time.sleep(0.1)
    for i in range(1, steps + 1):
        t = i / steps
        _mouse(kCGEventLeftMouseDragged, (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t))
        time.sleep(0.02)
    _mouse(kCGEventLeftMouseUp, p2)
    print(f"dragged ({x1},{y1}) -> ({x2},{y2})")


def scroll(app, x, y, dx, dy):
    activate(app)
    move(app, x, y)
    ev = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 2, int(dy), int(dx))
    CGEventPost(kCGHIDEventTap, ev)

# -------------------------------------------------------------- keyboard

KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9, "b": 11,
    "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21,
    "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31,
    "u": 32, "[": 33, "i": 34, "p": 35, "return": 36, "enter": 36, "l": 37, "j": 38, "'": 39,
    "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "tab": 48,
    "space": 49, "`": 50, "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126, "home": 115, "end": 119,
    "pageup": 116, "pagedown": 121, "forwarddelete": 117,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
}
MODS = {
    "cmd": Quartz.kCGEventFlagMaskCommand, "command": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift, "alt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate, "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
}


def key(app, combo, hold=0.05):
    activate(app)
    parts = combo.lower().split("+")
    flags = 0
    for m in parts[:-1]:
        flags |= MODS[m]
    name = parts[-1]
    if name not in KEYCODES:
        sys.exit(f"unknown key {name!r}")
    code = KEYCODES[name]
    down = CGEventCreateKeyboardEvent(None, code, True)
    up = CGEventCreateKeyboardEvent(None, code, False)
    CGEventSetFlags(down, flags); CGEventSetFlags(up, flags)
    CGEventPost(kCGHIDEventTap, down); time.sleep(hold)
    CGEventPost(kCGHIDEventTap, up)
    print(f"key {combo}")


def type_text(app, text, delay=0.04):
    activate(app)
    for ch in text:
        if ch.lower() in KEYCODES and ch.lower() == ch:
            # real keycode where possible (Flash reads keyCode, not just chars)
            code = KEYCODES[ch]
            down = CGEventCreateKeyboardEvent(None, code, True)
            up = CGEventCreateKeyboardEvent(None, code, False)
        elif ch.lower() in KEYCODES:
            code = KEYCODES[ch.lower()]
            down = CGEventCreateKeyboardEvent(None, code, True)
            up = CGEventCreateKeyboardEvent(None, code, False)
            CGEventSetFlags(down, Quartz.kCGEventFlagMaskShift)
            CGEventSetFlags(up, Quartz.kCGEventFlagMaskShift)
        else:
            down = CGEventCreateKeyboardEvent(None, 0, True)
            up = CGEventCreateKeyboardEvent(None, 0, False)
            CGEventKeyboardSetUnicodeString(down, len(ch), ch)
            CGEventKeyboardSetUnicodeString(up, len(ch), ch)
        CGEventPost(kCGHIDEventTap, down); time.sleep(0.02)
        CGEventPost(kCGHIDEventTap, up); time.sleep(delay)
    print(f"typed {text!r}")

# ------------------------------------------------------------------ main

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app", default=os.environ.get("CU_APP"), help="target app name (default: $CU_APP, else the frontmost app)")
    p.add_argument("--screen", action="store_true", help="coordinates are absolute screen points, not window-relative")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("windows")
    sub.add_parser("activate")
    s = sub.add_parser("screenshot"); s.add_argument("use_case", help="short motivation, e.g. after-plug-AE"); s.add_argument("--grid", type=int, default=0)
    s.add_argument("--region", help="X,Y,W,H in screen points; capture that area instead of a window")
    s.add_argument("--full", action="store_true", help="keep 1:1 point resolution (default: long side <= 1200 px)")
    s = sub.add_parser("click"); s.add_argument("x", type=float); s.add_argument("y", type=float)
    s.add_argument("--double", action="store_true"); s.add_argument("--right", action="store_true")
    s = sub.add_parser("move"); s.add_argument("x", type=float); s.add_argument("y", type=float)
    s = sub.add_parser("drag"); [s.add_argument(n, type=float) for n in ("x1", "y1", "x2", "y2")]
    s = sub.add_parser("type"); s.add_argument("text")
    s = sub.add_parser("key"); s.add_argument("combo")
    s = sub.add_parser("scroll"); [s.add_argument(n, type=float) for n in ("x", "y", "dx", "dy")]
    a = p.parse_args()
    if a.screen:
        a.app = "<screen>"
    elif not a.app and a.cmd not in ("windows",):
        a.app = frontmost_app()
        if not a.app:
            sys.exit("no --app given and no frontmost app found")

    if a.cmd == "windows":
        for w in list_windows():
            print(f"{w['id']:>6} {w['app']:<20} {w['x']:>5},{w['y']:<5} {w['w']}x{w['h']}  {w['title']}")
    elif a.cmd == "activate": activate(a.app)
    elif a.cmd == "screenshot":
        region = tuple(int(v) for v in a.region.split(",")) if a.region else None
        screenshot(a.app, a.use_case, a.grid, region, a.full)
    elif a.cmd == "click": click(a.app, a.x, a.y, a.double, a.right)
    elif a.cmd == "move": move(a.app, a.x, a.y)
    elif a.cmd == "drag": drag(a.app, a.x1, a.y1, a.x2, a.y2)
    elif a.cmd == "type": type_text(a.app, a.text)
    elif a.cmd == "key": key(a.app, a.combo)
    elif a.cmd == "scroll": scroll(a.app, a.x, a.y, a.dx, a.dy)


if __name__ == "__main__":
    main()
