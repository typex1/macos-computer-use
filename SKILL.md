---
name: macos-computer-use
description: See and operate the Mac the agent runs on. Semantic-first computer use for macOS - accessibility tree and Chrome DevTools before pixels, with on-device OCR and screenshots as fallback. Use when asked to open, read, click, type into or verify any desktop app, browser tab, menu-bar item or dialog on this Mac.
---

# macOS computer use

Three ways to see and act, in order of preference. Screenshots are the slowest
and least precise step; use them for understanding and final verification, not
as the first move.

| Order | Target | Tool | What you get |
|---|---|---|---|
| 1 | Chrome tabs (the user's real profile, logins, extensions) | `chrome-devtools` CLI | DOM snapshot with element uids; click/fill by uid; JS eval |
| 2 | Native and Electron apps, menu bar, dialogs | `scripts/ax.py` | UI element tree: role, title, state, exact frame; press by title |
| 3 | Canvas content with text (Flash, games, remote desktops, PDFs rendered as images) | `scripts/ocr.py` | on-device OCR, text lines with clickable centres |
| 4 | Anything, for understanding and verification | `scripts/cu.py screenshot` | downscaled PNG |
| act | any window or screen point | `scripts/cu.py click/type/drag/key/scroll` | synthetic mouse and keyboard |

Setup, once per machine: run `setup.sh` in this skill's folder. It creates
`.venv`, installs dependencies and checks permissions. Then:

    PY=<skill-dir>/.venv/bin/python
    $PY <skill-dir>/scripts/ax.py ...

## Workflow

1. **Identify the target.** `ax.py apps`, `cu.py windows`, `ax.py menubar`,
   `chrome-devtools list_pages`. `ax.py focused` tells you what the user is
   looking at right now.
2. **Get structure without pixels.** `ax.py --app X find "label"` (add
   `--role Button`, `--exact` for short labels like digits), `ax.py --app X
   tree`, `ocr.py --app X --find "label"`, `chrome-devtools take_snapshot N`.
3. **Act.** `ax.py --app X click "label" --role Button --exact` (uses the
   AXPress action, falls back to clicking the element's centre),
   `chrome-devtools click N <uid>`, or `cu.py --app X click CX CY` with
   coordinates from step 2.
4. **Verify cheaply.** `ax.py focused`, `ax.py find`, `ocr.py --find`, or a new
   `take_snapshot`. Take a screenshot only when the state is visual (colours,
   drawings, highlights) or the structured tools disagree with expectations.

Never assume an action worked. Clicking a label instead of its field does
nothing; Return may confirm a suggestion instead of submitting; substring
matches hit the wrong button ("1" matched "10 to the X" until `--exact`).

Ask before irreversible or disruptive actions: sending messages, deleting,
paying, installing updates that quit the user's apps. Open your own browser
tab for new work; do not navigate or close the user's tabs unless asked.

## Memory: notes are durable, screenshots are not

- **`app-notes/<app>.md`** in the current workspace: what you learned about an
  app (element titles that work, layout, quirks, verified flows). Read the
  note before acting on an app; append when you learn something. This is the
  knowledge that compounds across sessions. Keep it text; never paste
  coordinates that only hold for one window size without saying so.
- **Screenshots** are working memory for the current task. `cu.py` writes them
  to `./.computer-use/screenshots/cu_<use-case>.png` and keeps only the newest
  20 (`CU_KEEP`), deleting older ones automatically. Name each capture by its
  motivation (`login-form-filled`, `updates-list-open`) so the latest set reads as
  a trail. Add `.computer-use/` to `.gitignore`. If a picture is worth
  keeping, describe what it showed in the app note instead.

## cu.py (pixel layer)

    cu.py --app "<App>" windows|activate|screenshot USE-CASE [--grid 50] [--full] [--region X,Y,W,H]
    cu.py --app "<App>" click X Y [--double] [--right] | drag X1 Y1 X2 Y2 | type TEXT | key cmd+c | scroll X Y DX DY | move X Y
    cu.py --screen click X Y                   # absolute screen points (menu bar, Dock, dialogs)

`--app` defaults to `$CU_APP`, else the frontmost app. Window-relative
coordinates equal the pixel coordinates of a `--full` screenshot. Default
screenshots downscale the long side to 1200 px and print the factor; take
coordinates from `ax.py`/`ocr.py` rather than from a scaled image. `--grid`
overlays a labelled grid (implies `--full`). Menu bar strip:
`--region 0,0,<screen-width>,25`. `type` sends real key codes so apps that
read keyCode (Flash, games) work; `key` takes `cmd|shift|alt|ctrl` prefixes.

## ax.py (accessibility layer)

    ax.py apps | menubar | focused
    ax.py --app X tree [--depth N] [--all]          # --all keeps empty groups
    ax.py --app X find "text" [--role R] [--exact]
    ax.py --app X click "text" [--role R] [--exact] [--nth K]
    ax.py menubar-click "<owner app or title>"

Frames are absolute screen points. Electron apps (Slack, Teams, VS Code,
draw.io) build their tree on the first call; if `find` is empty, call once
more. Virtualised lists expose only rendered rows. Checkbox and radio state,
disabled buttons and focus are reported. Canvas content (Flash, WebGL, custom
drawing) is opaque to AX.

## ocr.py (on-device OCR, Apple Vision)

    ocr.py --app X [--find "text"] [--fast]
    ocr.py --region X,Y,W,H [--find "text"]

Prints `cx,cy text [w x h confidence]`; coordinates are ready for
`cu.py --app X click` (window mode) or `cu.py --screen click` (region mode).
About 1.5 s; nothing leaves the Mac. Labels and buttons are reliable; single
glyphs in decorative fonts are noisy.

## chrome-devtools CLI (Chrome layer)

Attaches to the user's running Chrome through Chrome's built-in permission at
`chrome://inspect/#remote-debugging` (Chrome 144+). No browser extension, no
side profile, so corporate SSO sessions and extensions carry over. Chrome
shows an Allow dialog on first attach.

    export CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1
    chrome-devtools start --autoConnect --workspace="$PWD"     # once per session
    chrome-devtools list_pages | new_page URL | select_page N | navigate_page N --url URL
    chrome-devtools take_snapshot N                            # a11y tree with uids
    chrome-devtools click N <uid> | fill N <uid> "text"
    chrome-devtools evaluate_script "() => document.title" --pageId N
    chrome-devtools take_screenshot N --filePath "$PWD/.computer-use/screenshots/cu_<use-case>.png"
    chrome-devtools close_page N | stop

Uids change after navigation; re-snapshot before clicking. `take_screenshot`
only writes inside `--workspace`.

## Limits

- macOS only. Permissions (Accessibility, Screen Recording) belong to the app
  hosting the agent's shell; `setup.sh` names it and opens the right pane.
- Firefox and Safari have no semantic page layer here: use `ax.py` for browser
  chrome, `ocr.py`/`cu.py` for page content, `open -a Firefox <url>` to
  navigate.
- Secure input fields (password prompts) block synthetic keyboard events by
  design.
