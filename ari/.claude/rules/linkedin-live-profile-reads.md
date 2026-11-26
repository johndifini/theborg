---
name: linkedin-live-profile-reads
description: "When reading a live LinkedIn profile in Chrome: wait after navigating, check the URL line, scroll to the end before get_page_text, and never report an entry missing from one read."
---
# Reading a live LinkedIn profile

LinkedIn is a single-page app that lazy-loads its lists. On 2026-11-20 a
get_page_text right after navigating to /details/experience/ returned the
main profile page, and a later read stopped partway down the Experience
list. The session told the user an entry was missing; it was there.

- After navigate, wait about 3 seconds, and check that the returned URL:
  line is the page you asked for before using the text.
- On /details/experience/ and /details/skills/, scroll down until a
  screenshot shows the end of the list, then call get_page_text.
- Never report an entry, skill, or section as missing on the strength of
  one read. Say where the read stopped (the last entry it returned) and
  confirm with a screenshot of the end of the list first.
- "Security check failed: the page navigated to a different domain" means
  the page redirected during the read. Call tabs_context_mcp and read again.
