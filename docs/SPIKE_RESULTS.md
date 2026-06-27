# Spike Results — Auto-Tab-Select Validation

**Date:** Jun 26, 2026
**Operator:** Rinoah
**Time spent:** ~5 minutes
**Outcome:** ✅ PASS (with implementation nuance documented below)

---

## What was tested

Whether Playwright-launched Chromium with these flags bypasses the native `getDisplayMedia` picker when ScreenFlow's record button is clicked:

```
--auto-select-tab-capture-source-by-title=Prospect-test
--enable-features=AutoSelectTabCaptureSourceByTitle
--use-fake-ui-for-media-stream
--autoplay-policy=no-user-gesture-required
--disable-blink-features=AutomationControlled
```

Two tabs were opened in the Playwright Chromium window:
1. ScreenFlow recorder (served at `http://localhost:8765/screenflow/index.html`)
2. `Prospect-test` page (served at `http://localhost:8765/prospect_test.html`, document title = `Prospect-test`)

Spike code: `spike/spike.py` (preserved in this repo as a smoke test).

---

## Result

**Picker bypass: confirmed.** No native browser dialog appeared when clicking record. Recording started immediately.

Two recordings were captured during the spike:

| # | Duration | Size | What it captured | Note |
|---|---|---|---|---|
| 1 | 5s | 1.1 MB | The ScreenFlow tab itself | Operator clicked record while ScreenFlow was the focused tab |
| 2 | 9s | 1.5 MB | The `Prospect-test` page | Operator switched to Prospect tab before clicking record |

---

## What we learned

The flag combination bypasses the picker but **tab selection is foreground-driven, not strictly title-matched.** The `--auto-select-tab-capture-source-by-title` flag may or may not be doing work; `--use-fake-ui-for-media-stream` appears to auto-accept whatever the foreground tab is at the moment `getDisplayMedia` fires.

This is a **better** outcome than the original plan, because:

1. **No need to switch tab focus to ScreenFlow before clicking record** — we can trigger the record button via Playwright JS evaluation while the Prospect tab stays foreground:
   ```python
   await prospect_page.bring_to_front()  # Prospect is foreground
   await screenflow_page.evaluate(
       "() => document.querySelector('#btn-record').click()"
   )
   # getDisplayMedia fires, auto-accepts the foreground (Prospect) tab.
   ```

2. **Eliminates the title-matching dependency** — no need to set `document.title` on the prospect page or coordinate it with the launch flag.

3. **More predictable** — foreground focus is something we control explicitly via `bring_to_front()`.

---

## Implementation lock-in for Pipeline 3

The Terminator Loom recorder will use this pattern:

```python
# 1. Open prospect URL in new tab
prospect_page = await context.new_page()
await prospect_page.goto(prospect_url)
await prospect_page.bring_to_front()  # Prospect becomes foreground

# 2. Configure ScreenFlow via DOM in the background tab
await screenflow_page.evaluate("""
    () => {
        document.querySelector('#toggle-mic').checked = false;
        document.querySelector('#toggle-audio').checked = true;
        document.querySelector('#setting-filename').value = 'First_Last';
        // ... auto-stop timer, etc.
    }
""")

# 3. Trigger record from ScreenFlow tab without switching focus
await screenflow_page.evaluate(
    "() => document.querySelector('#btn-record').click()"
)
# getDisplayMedia fires, foreground (Prospect) tab gets auto-selected.

# 4. Inject MP3 audio element into prospect tab
await prospect_page.evaluate("""
    () => {
        const audio = new Audio('http://localhost:8765/assets/master_pitch.mp3');
        audio.play();
    }
""")

# 5. Scroll the prospect page (immediate down, then back up, then slow scroll)
# 6. Wait for auto-stop timer to fire
# 7. Switch to library tab, click download, intercept with page.expect_download()
```

ScreenFlow DOM selectors (`#btn-record`, `#toggle-mic`, `#toggle-audio`, `#setting-filename`) need to be verified during Pipeline 3 build — values above are inferred from `app.js` symbol names (`dom.toggleMic`, `dom.toggleAudio`, `dom.settingFilename`).

---

## Open follow-ups for Pipeline 3 build

1. **Verify exact ScreenFlow DOM selectors** by inspecting the actual `index.html` during build (5 min — included as a build spec acceptance criterion).
2. **Confirm WebM vs MP4 output** on Playwright's bundled Chromium. ScreenFlow's `app.js` tries `video/mp4;codecs=avc1` first — if the bundled Chromium build supports H.264, we get MP4 natively; otherwise WebM, and FFmpeg post-process transcodes. Spike output is WebM.
3. **Test programmatic record without window focus** — spike used a visible Chromium window; production may run with the window in the background. Should still work since Playwright drives via the page API, not OS-level clicks, but worth verifying.

---

## Reproducing the spike

```bash
cd spike
pip install -r requirements.txt
playwright install chromium
python spike.py
```

Then in the Chromium window that opens:
1. Click into the ScreenFlow tab (left tab)
2. Click the gear icon (settings)
3. Mic OFF, System Audio ON
4. Click the big record button

Pass if no picker appears. Fail if a native "choose what to share" dialog opens.

---

## Why this matters

Decision #2 in `OPS-61_PLAN.md` puts the recorder on Rinoah's local machine, with the entire Pipeline 3 architecture depending on Playwright driving ScreenFlow programmatically. The picker dialog was the single thing that could have blocked full automation. With it bypassed, Pipeline 3 builds as planned.
