---
name: yt2sub
description: >
  Transcribes a YouTube video or local audio/video file to plain text with
  ./fw yt2sub. Use when a task needs spoken content as text: the user gives a
  YouTube URL or media file to transcribe, summarize, or 觀看, or wants notes or
  an assignment written from a talk, lecture, or podcast. Tries YouTube captions
  first (zh-Hant/en) and falls back to local faster-whisper, so use it instead
  of a hand-rolled yt-dlp + whisper pipeline.
---

# yt2sub — YouTube / audio → text

The framework ships `./fw yt2sub` (run from the course root). This skill is the entry point for "watch/transcribe this video" requests; the script is the implementation. **Run — and extend — `./fw yt2sub` rather than building your own yt-dlp + whisper pipeline or calling a transcription API.**

## How it works

1. **Captions first.** For a YouTube URL it fetches YouTube's own caption track and cleans it to plain text — near-instant, no GPU/CPU cost. Language preference is `en, en-US, en-GB, zh-Hant, zh-TW, zh-Hans, zh, ja, ko`; the first track that exists wins.
2. **Whisper fallback.** If no usable captions exist (or the input is a local audio file, or you pass `--whisper`), it downloads the audio and transcribes with `faster-whisper` (`large-v3-turbo`, CPU, int8). This is accurate but slow (~real-time on CPU).

## Usage

```bash
./fw yt2sub <youtube-url|audio-file> [output-dir]   # default out: cwd
./fw yt2sub --whisper <url|file> [output-dir]        # skip captions, force ASR
```

Output is written to `<output-dir>/<title>.txt`; the final stdout line is `Done: <path>`. The transcription method is reported on stderr (`(via captions)` / `(via whisper)`).

Env knobs:
- `YT2SUB_LANGS` — override the caption language preference, e.g. `YT2SUB_LANGS="ja,en" ./fw yt2sub <url>`.
- `WHISPER_MODEL` — Whisper model for the fallback (default `large-v3-turbo`).

## When to reach for each path

- **Captions** are ideal when you just need to *read/understand* the content (summaries, reflections, homework). They reflect the spoken language; for an English talk you get English text to write Chinese notes from.
- **Whisper** (`--whisper`) when the video has no captions, when captions are auto-translations you don't trust, or for a local recording.

## Setup / dependencies

- `yt-dlp` (`uv tool install yt-dlp`) — required for any URL. Invoke yt-dlp with `--js-runtimes node` (local node); **do not** add `--remote-components ejs:github` — it pulls and runs remote JS and the sandbox classifier denies it (the script already omits it).
- `python3` — for caption cleaning (present by default on macOS).
- Whisper fallback only: `ffmpeg`, and a venv at `~/tools/yt2sub/venv` with `faster-whisper` (`uv venv ~/tools/yt2sub/venv && uv pip install --python ~/tools/yt2sub/venv/bin/python faster-whisper`).

## Gotchas

- YouTube's timedtext (caption) endpoint rate-limits (`HTTP 429`) easily. The script requests **one language at a time** to stay under it; if it still 429s for every language, it falls back to Whisper automatically.
- The caption cleaner keeps only the finalized lines of YouTube's rolling auto-caption format, so the text is complete and non-overlapping — but it is not a verbatim, punctuation-perfect transcript. Good for comprehension and writing; use `--whisper` if you need higher fidelity.
