#!/usr/bin/env python
"""ocr.py - on-device OCR (Apple Vision) of an app window or a screen region.
Prints each recognised text line with its centre in CLICKABLE coordinates:
window-relative for --app (feed to `cu.py --app X click`), absolute for --region
(feed to `cu.py --screen click`). Nothing leaves the Mac.

Usage:
  ocr.py --app NAME [--find TEXT] [--fast]
  ocr.py --region X,Y,W,H [--find TEXT] [--fast]
"""
import argparse
import os
import sys

import Quartz
import Vision
from Foundation import NSURL

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cu import find_window  # noqa: E402


def capture(app, region):
    if region:
        x, y, w, h = region
        win = {"x": x, "y": y, "w": w, "h": h}
        img = Quartz.CGWindowListCreateImage(
            Quartz.CGRectMake(x, y, w, h), Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID, 0)
    else:
        win = find_window(app)
        img = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, win["id"],
            Quartz.kCGWindowImageBoundsIgnoreFraming)
    if img is None:
        sys.exit("capture failed (Screen Recording permission?)")
    return img, win


def recognise(cgimage, fast):
    results = []

    def handler(request, error):
        if error:
            sys.exit(f"Vision error: {error}")
        results.extend(request.results() or [])

    req = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast if fast
                             else Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    handler_ = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cgimage, None)
    ok, err = handler_.performRequests_error_([req], None)
    if not ok:
        sys.exit(f"Vision failed: {err}")
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app", default=os.environ.get("CU_APP"), help="target app (default: $CU_APP, else frontmost app)")
    p.add_argument("--region", help="X,Y,W,H screen points")
    p.add_argument("--find", help="only lines containing this text (case-insensitive)")
    p.add_argument("--fast", action="store_true", help="fast recogniser (less accurate)")
    a = p.parse_args()
    region = tuple(int(v) for v in a.region.split(",")) if a.region else None
    if not region and not a.app:
        from cu import frontmost_app
        a.app = frontmost_app()

    img, win = capture(a.app, region)
    W, H = win["w"], win["h"]  # logical points; Vision returns normalised coords
    lines = []
    for obs in recognise(img, a.fast):
        cand = obs.topCandidates_(1)
        if not cand:
            continue
        text = cand[0].string()
        bb = obs.boundingBox()  # normalised, origin bottom-left
        x = bb.origin.x * W
        y = (1 - bb.origin.y - bb.size.height) * H
        w, h = bb.size.width * W, bb.size.height * H
        if region:
            x += win["x"]; y += win["y"]
        lines.append((y, x, text, w, h, cand[0].confidence()))
    lines.sort()
    needle = a.find.lower() if a.find else None
    origin = "screen" if region else f"window-relative ({a.app})"
    print(f"# {len(lines)} lines, coords {origin}, format: cx,cy  text  [w x h conf]")
    for y, x, text, w, h, conf in lines:
        if needle and needle not in text.lower():
            continue
        print(f"{int(x + w / 2):>5},{int(y + h / 2):<5} {text}  [{int(w)}x{int(h)} {conf:.2f}]")


if __name__ == "__main__":
    main()
