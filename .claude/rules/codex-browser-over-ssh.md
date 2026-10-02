---
name: codex-browser-over-ssh
description: "When a Codex session reports no browser backend: it is usually running over SSH, not broken — the in-app browser lives in ChatGPT Desktop's GUI session on the MacBook and is not forwarded. Check before promising any browser-based verification."
---
# "Browser is not available" in Codex means check SSH first

The browser bridge is attached to ChatGPT Desktop's GUI session on the MacBook.
A Codex task executing over SSH on the Mac Studio cannot see it — SSH forwards
the agent, not the native browser bridge. The plugin is installed, the control
runtime starts normally, config expects both `iab` and `chrome`, and discovery
still returns `[]`. Nothing is broken.

Diagnose in one step, before starting any work that ends in a browser check:

```sh
[ -n "$SSH_CONNECTION" ] && echo "remote session — no browser bridge"
```

Symptoms that all mean this same thing, and are not separate faults:

- `Browser is not available: iab`
- browser discovery returns `[]` while the plugin reports installed and enabled
- `cgWindowNotFound` from Chrome *and* from Finder
- opening the panel "queues" without ever initializing a backend

**Do not** spend a turn re-deriving this: retrying the panel, relaunching Chrome
by bundle identifier, opening Finder, or enabling Computer Use (a different
surface) will not attach a browser.

**Do not** substitute a terminal fetch or source inspection for a rendered check
and call the gate passed. A runtime or visual criterion is not satisfiable from
source; say it is blocked and why.

Recovery, in order:

1. Run the task from the local ChatGPT Desktop app on the machine with the GUI.
   This is the reliable fix — verified 2026-09-04, when the same task that had
   been blocked on the Studio completed its full browser gate locally.
2. Drive a local browser headlessly instead. Chrome is installed on the
   Studio; launching it headless and measuring through the DevTools protocol
   yields a genuine rendered result — computed geometry, focus rings,
   light/dark, and narrow-viewport reflow — and satisfies a rendered gate.
   Verified 2026-09-20 in `ari/career-dossier` and 2026-09-26 in `repos/atm`.
   This is not the terminal-fetch substitute forbidden above: the page is
   actually laid out and painted.
3. If the work must stay on the Studio, open a visible Chrome window *there* and
   reconnect accessibility. A hidden or windowless Chrome yields
   `cgWindowNotFound`.
4. File-upload work needs one more step even once the browser attaches:
   `chrome://extensions` → the ChatGPT extension → Details → enable **Allow
   access to file URLs**, or the file chooser never opens.

State the constraint up front when a task's acceptance criteria are visual, so
the user can choose the host before the work is done rather than after.

The same wall appears in Claude Code, not only Codex. `claude-in-chrome`'s
`list_connected_browsers` returns `[]` until a Chrome with the extension is
connected; once the Studio's own Chrome is connected, a Studio SSH session
can drive it (verified 2026-09-29). Whether a Chrome on the MacBook is
reachable from a Studio session is untested. `computer-use` is a separate
surface and stays blocked until Claude Desktop is granted macOS
Accessibility and Screen Recording permission. Reach for headless Chrome
before asking the user to grant anything.

Observed in eight Codex sessions between 2026-09-02 and 2026-09-07, mostly in
`ari/career-dossier`, each re-deriving the diagnosis from scratch before either
giving up or — once — finding the cause.
