# OPS-61 Spike — Auto-Tab-Select Validation

**Time required:** ~5 minutes
**Blocks:** Pipeline 3 (Terminator Loom Recorder) build
**Output expected:** clear pass/fail screenshot

---

## What this validates

Pipeline 3 plans to use a Chromium launch flag (`--auto-select-tab-capture-source-by-title`) to bypass the native `getDisplayMedia` picker. This lets Playwright drive ScreenFlow's record button without any human-in-the-loop click on a browser dialog.

If the flag works → Pipeline 3 builds as planned (full automation).
If the flag fails → we fall back to a different approach (see "If it fails" below).

This spike just answers that one question.

---

## Setup (one-time, ~2 min)

You need Python 3.9+ already installed.

```bash
cd ops61-spike
pip install -r requirements.txt
playwright install chromium
```

---

## Run

```bash
python spike.py
```

A Chromium window opens with two tabs:
1. ScreenFlow (the recorder, focused)
2. `Prospect-test` (a stand-in prospect page)

**In the ScreenFlow tab:**
1. Open Settings (gear icon)
2. Mic: **OFF**, System Audio: **ON**
3. Click the big **RECORD** button

---

## Pass / Fail

### ✅ PASS
- Recording starts **immediately**
- **No** native picker dialog appears
- The recording captures the `Prospect-test` tab content
- → **Pipeline 3 builds as planned. Tell me and I'll write Build Spec #3.**

### ❌ FAIL
- Chrome shows a native dialog asking which tab/window/screen to share
- → **We need a fallback. See below.**

Either way: screenshot the moment after clicking RECORD and post in Discord.

Press `Ctrl+C` in the terminal when done.

---

## If it fails

Three fallback options, in order of preference:

### Fallback A: drop the auto-select flag, keep `--use-fake-ui-for-media-stream` alone
Less precise (may pick the wrong default source) but auto-accepts whatever's selected. Quick to test — just remove the first two flags from `spike.py` and re-run. If the default selection is the foreground tab, this works.

### Fallback B: fork ScreenFlow to expose a `startRecordingWithTab(tabId)` JS function
Adds a hook bypassing `getDisplayMedia`'s picker. Requires modifying `app.js`. Cleanest but breaks the "keep ScreenFlow unforked" decision from the plan (#9). Acceptable tradeoff if A and C both fail.

### Fallback C: ditch tab-capture, use full-screen capture instead
Capture entire screen, crop in FFmpeg to the prospect window's region. Works on any setup but adds FFmpeg complexity and requires window position management.

---

## Why this matters

Decision #2 in OPS-61_PLAN.md puts the recorder on Rinoah's local box for v1. The whole architecture depends on Playwright being able to drive ScreenFlow programmatically. The picker dialog is the single thing that could block that. We need to know now, not three days into the Pipeline 3 build.
