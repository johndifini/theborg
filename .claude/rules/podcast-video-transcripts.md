---
name: podcast-video-transcripts
description: "When you need what a podcast episode or YouTube video actually says: look for the publisher's transcript first; yt-dlp captions get HTTP 429 here; transcribe feed audio with faster-whisper; identify a Spotify chapter's episode by date, not topic."
---
# Getting the words of a podcast or video

- **Publisher transcript first.** Many shows post one. The AI Daily Brief
  serves `https://aidailybrief.ai/e/<YYYY-MM-DD>/transcript.md` (timestamped)
  and `/e/<YYYY-MM-DD>.md` (notes), verified 2026-11-18.
- **yt-dlp captions get HTTP 429 from YouTube here** ("Unable to download
  video subtitles for 'en': HTTP Error 429"), even with `--sleep-subtitles`
  and long pauses: 5 of 6 videos failed on 2026-10-17, and every try on
  2026-11-18. Metadata (`--write-info-json`, `--print description`) still
  works. Try captions once, then move on. Don't rotate `player_client` to
  get past the limit: the auto-mode classifier denied that as unauthorized
  access (2026-11-18). last30days' "stale yt-dlp" hint for missing YouTube
  transcripts may be this same limit.
- **No transcript and no captions:** take the episode MP3 from the show's RSS
  `<enclosure>` and transcribe it with `faster-whisper` in a venv under the
  workspace `tmp/` (`python3.12 -m venv`; it decodes MP3 without ffmpeg).
  It is slow, so say so. The Studio has no whisper CLI or ffmpeg.
- **A Spotify `podcast-chapter` page doesn't name its episode.** Match it by
  date against the show's feed, not by topic, and call the match unconfirmed
  until the dates agree. On 2026-11-18 a topic match chose a 2025 episode
  over a chapter dated 2026, and the summary was of the wrong episode.
