# Pipeline 3 — Terminator Loom Auto-Recorder

> Awaiting Build Spec. Will be populated by a focused Claude Code session.

See `OPS-61_PLAN.md` "Pipeline 3 — Terminator Loom Auto-Recorder" for the full spec.
See `docs/SPIKE_RESULTS.md` for the validated implementation pattern.

**Quick summary:**
- Python + Playwright + bundled ScreenFlow + FFmpeg
- Auto-records customized prospect videos using master MP3 pitch
- Picker bypass validated by Jun 26 spike; foreground-tab capture pattern locked
- Output: `[First_Name]_[Last_Name].mp4` with circular profile pic overlay bottom-left, uploaded to Drive

**Depends on (v0 setup):**
- Master MP3 at `assets/master_pitch.mp3` (Jon, 1–2 min pitch)
- Profile pic at `assets/profile_overlay.png` (Jon, professional headshot, 1024x1024)
