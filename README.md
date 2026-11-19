# macos-computer-use

An agent skill that lets a coding agent see and operate the Mac it runs on.
Semantic first: accessibility tree (`ax.py`) and Chrome DevTools before pixels,
on-device OCR (`ocr.py`) for canvases, screenshots (`cu.py`) as fallback.

Install: copy this folder to your agent's skills directory
(`~/.kiro/skills/`, `.kiro/skills/`, `~/.claude/skills/` ...) and run
`setup.sh` once. The agent reads `SKILL.md` for everything else.

Requirements: macOS, Python 3.10+, optional Node.js and Google Chrome 144+ for
the Chrome layer. Grants needed: Accessibility and Screen Recording for the app
that hosts the agent's shell.

Screenshots are ephemeral (newest 20 kept under `./.computer-use/screenshots`);
durable knowledge goes to `app-notes/*.md` as text.
