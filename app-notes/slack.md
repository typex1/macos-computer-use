# Slack (desktop, Electron)

Prefer `ax.py --app Slack`; the full UI is exposed once Electron accessibility
is on (the first `ax.py` call enables it; retry once if `find` is empty).
The window title names the open conversation, e.g.
"<name> (DM) - <workspace> - Slack" or "#<channel> - <workspace> - Slack".

## Anchors

- Left rail: `RadioButton 'Home | 0'`, `'DMs | 0'`, `'Activity | 0'`,
  `'Files | 0'`. `ax.py --app Slack click "DMs" --role RadioButton` switches
  views via AXPress.
- Top search: `Button 'Search <workspace>'`, or `Button 'Search: <query>'`
  while a query is active. Typing `from:me` resolves to `from:@<user>`;
  pressing Return only confirms the suggestion. Click the "Show results for"
  row to run the search.
- Search results: cards sorted "Newest" first; destination appears as
  `StaticText 'Direct Message with <name>'` or the member list for group DMs.
  Default filter "Last 7 days".
- Message rows are `Group` elements whose text is the whole message
  ("You to <name>: <text> <date>"), so `find "You to"` lists what the user
  wrote in the open conversation.
- Composer: `TextField`/`TextArea` with "Message <conversation>" placeholder at
  the bottom. Ask before sending anything.

## Verified

- A `from:me` search answered "to whom did I write my last message" from the
  result cards without a screenshot.
