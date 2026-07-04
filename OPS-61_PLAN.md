# OPS-61 — Full-Stack Lead Generation & Automation Engine

**Status:** PLAN v9 — mock-based dev + credentials-at-migration model locked (Decision #12 + OAuth-defer corollary). Foundation + Loomless (Pipeline 1, Build Spec #2) SHIPPED to main (`fa63f00`, 2026-07-05). **Next: Pipeline 2 — JV Research Bot.**
**Owner:** Rinoah (solo dev), Jon (direction)
**Due:** Jul 3
**Linear:** OPS-61
**Source spec:** EasyGrow client acquisition program

---

## Objective

Build a hands-free machine that handles all the tedious prep for outbound: high-volume personalized copy, customized video recording, JV research, and instant inbound capture from the FB Group.

## Core constraint (non-negotiable)

**Automation stops at asset creation and data logging.** No SMTP/Gmail API/social media messaging API calls outbound. No automated sends. Operator manually sends everything. This protects deliverability and account health.

## Volume target (v1)

- **Loomless:** 100 leads/day (scale to 400/day in v2)
- **Terminator Loom:** 10–20 videos/day (operator-bottlenecked on manual send anyway)
- **JV Research:** ~20 prospects/week
- **FB Inbound:** reactive, capped by FB Group join rate

Sized for solo dev (Rinoah) executing v1 alone.

---

## Tech stack (locked)

| Layer | Choice |
|---|---|
| Workflow engine | Self-hosted n8n (existing Hostinger VPS) |
| LLM — copy | Claude Max API |
| LLM — research | Perplexity Pro API |
| CRM / system of record | Google Sheets |
| Video storage | Google Drive |
| Browser automation | Playwright (Python) |
| Screen recording | **ScreenFlow** (bundled internal web app, runs locally) |
| Video post-process | FFmpeg (overlay filter only, no audio routing needed) |
| FB Group capture | Chrome extension (see Decision #4) |
| Notifications | Discord (reuse FC IG Lead Discovery webhook pattern) |
| Runtime for recorder | Rinoah's local dev box (v1) |

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│              GOOGLE SHEETS CRM (system of record)               │
│   tabs: Loomless | JV_Targets | Terminator_Loom | Inbound      │
└─────────────────────────────────────────────────────────────────┘
         ▲              ▲              ▲              ▲
         │              │              │              │
   ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴──────┐  ┌────┴──────┐
   │ Loomless  │  │    JV     │  │ Terminator │  │ FB Group  │
   │ Pipeline  │  │ Research  │  │   Loom     │  │  Router   │
   │           │  │   Bot     │  │  Recorder  │  │           │
   │   (n8n)   │  │   (n8n)   │  │ (Playwright│  │ (Chrome   │
   │           │  │           │  │ +ScreenFlow│  │  ext +    │
   │           │  │           │  │  +FFmpeg)  │  │  n8n)     │
   └───────────┘  └───────────┘  └────────────┘  └───────────┘
        │              │              │                │
        ▼              ▼              ▼                ▼
  First lines   JV prospects   Custom videos    Warm FB leads
   in Sheets    in Sheets     in Drive +        in Sheets
                              Sheets link

           ┌──────────────────────────────────────────┐
           │  Discord HITL — operator review + send   │
           └──────────────────────────────────────────┘
```

---

## Reuse from existing FC infrastructure

| Component | Source project | Use case |
|---|---|---|
| Google Sheets + n8n sync pattern | FC IG Lead Discovery (pre-Supabase variant) | All 4 pipelines |
| Discord HITL operator loop | FC IG Lead Discovery | Operator review/send |
| Perplexity n8n integration | (build once, reuse) | Loomless + JV |
| Playwright headed pattern | posting-agent | Terminator Loom |
| Chrome extension capture pattern | LinkedIn Lead Capture (Rinoah) | FB Group router |
| Randomized human-delay helpers | posting-agent | All scraping |
| **ScreenFlow web recorder** | Jon's internal tool | Terminator Loom (replaces FFmpeg+OBS+OS audio loopback) |

New code: Terminator Loom recorder orchestrator + FB Group extension. Rest is remix.

---

## Decisions resolved

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | CRM | Google Sheets, per-pipeline tabs | Spec says so; 100/day fits Sheets easily; no Supabase tax for solo dev |
| 2 | Terminator Loom runtime | **Build:** Rinoah's local machine (dev + test). **Run:** company server machine (after handoff). | Solo dev builds and validates against a controlled local environment; handoff package migrates the whole stack (recorder + local Docker n8n + all pipelines) to the company server for production run. Removes prod deployment risk from every daily iteration. |
| 3 | Video hosting | Google Drive folder | Spec says so; operator already lives in Drive |
| 4 | FB Group capture | Chrome extension (diverge from spec) | Spec says "local browser script" but extension runs in admin's already-authenticated session = lowest detection risk + reuses Rinoah's proven LinkedIn pattern. Read-only DOM scrape — no clicks, no risk of auto-approve |
| 5 | First-line QA / auditor | OFF for v1 | Adds latency + cost; operator filters at send time; revisit if quality drops |
| 6 | Volume v1 | 100/day Loomless, 10–20/day video | Sized for solo dev; scale once deliverability proven |
| 7 | Master pitch MP3 | One universal MP3 v1 | Variants in v2 after we have data on which persona converts |
| 8 | JV bot trigger | Cron (weekly Mon 9am) + manual webhook | Cheap to have both; manual lets operator force a run on demand |
| 9 | Recording approach | ScreenFlow bundled locally + Playwright orchestration + FFmpeg overlay post-process | Kills OS-level audio loopback complexity; uses Jon's already-built internal tool; FFmpeg reduced to overlay filter only; ScreenFlow stays unforked + reusable |
| 10 | FB Group Q3 conversion question | **Option A — DM permission.** Exact wording: "Would you like me to reach out to discuss how we may be able to help you with that?" | Directly aligns with DM Sorcery flow; operator already manually approves + sends welcome voice note, so explicit DM permission at the gate eliminates friction into the Engaged stage. Prioritizes immediate client acquisition over list-building. When Q3=Yes lands in Sheet, operator action is unambiguous: skip warm-up, use Direct Intent reply scripts, drop Calendly |
| 11 | Profile pic overlay format | Static PNG default, animated GIF as opt-in config flag | Static is simpler + sufficient for v1 spec. GIF support adds ~5 lines of FFmpeg input flags; build it in but default off. EasyGrow notes GIF can boost preview view rate — A/B test in v2 |
| 12 | Credential provisioning timing | **Deferred to migration day (Build Spec #6).** All pipelines built with mocked API responses locally. No real Perplexity, Anthropic, Drive OAuth, or FB session credentials during dev. | Rationale: (a) all credentials get reset/replaced when project transfers to company server anyway, (b) Perplexity Pro is a real recurring cost not worth burning pre-migration, (c) Anthropic prompt-tuning burns tokens that will be redone anyway once real production leads flow, (d) cleaner separation between "workflow logic" (portable, git-tracked) and "credentials" (target-machine, secret). Tradeoff: prompt quality is untuned at ship time; first real batches during Build Spec #6 will need a focused tuning pass. |

**Decision #12 corollary (v9) — auth-node provisioning.** For ANY workflow node requiring OAuth or interactive account authorization (Drive Trigger, Chrome session tokens for BS#4, third-party service OAuth, etc.):

- Build the node **structurally now** — correct type, correct parameters, correct downstream wiring, and a sticky note explaining what it does.
- Leave the credential slot **UNWIRED** (or wire it to a **Service Account** where SA works).
- Real OAuth provisioning happens at **Build Spec #6** handoff on the target machine.

Rationale: Rinoah's dev account is never tied to production runs; the workflow stays portable across machines; dev-time credential setup burden drops; all auth work concentrates at handoff. **First application:** the Loomless **Drive Trigger** (Build Spec #2) is wired to the portable **OPS-61 Service Account** (reviewed + approved — the SA has editor on the inbox folder and is *not* a personal OAuth binding; it's replaced like all credentials at BS#6). It does **not** fire in dev — mock smoke tests run via a **Manual Trigger → "Fake Drive Payload"** entry alongside it; the Drive Trigger becomes the production entry at BS#6. (Nodes where SA does *not* work stay UNWIRED until BS#6 per the rule above.)

---

## Pipeline 1 — Loomless AI Personalization Pipeline

**Goal:** Generate hyper-personalized first lines for cold emails at 100/day.

**Flow:**
1. Operator uploads scraped CSV to a watched Google Drive folder
2. n8n trigger picks up new file
3. For each row, n8n calls Perplexity API: search web + LinkedIn for recent achievements, company news, personal context
4. n8n passes Perplexity summary + lead data to Claude API
5. Claude generates ONE first line per lead following copywriting rules below
6. n8n writes results to `Loomless` tab with new column `Personalized_First_Line` + `Research_Summary` + `status=ready_for_review`
7. Discord ping: "Loomless batch ready: 100 rows, link to Sheet"

**Inputs:** CSV with cols: Company Name, Owner Full Name, First Name, Email, Website
**Outputs:** Same rows in `Loomless` tab + `Personalized_First_Line`, `Research_Summary`, `status`, `created_at`

**Copywriting rules for Claude (locked):**
- Sound human, casual, highly relevant — NOT marketing-speak
- Specific to a recent event, achievement, or context point
- One sentence, conversational tone
- Examples that work:
  - "Saw you recently posted about your 40% close rate in December. Congrats!"
  - "Noticed on LinkedIn you're based in Ottawa. If we connect, I'd be happy to buy you lunch at Riviera!"
- If Perplexity returns no usable context, output `[NO_CONTEXT]` and let operator skip

**Perplexity prompt template:** TBD in build spec — should pull recent LinkedIn posts, podcast appearances, company news, press, hiring signals.

---

## Pipeline 2 — JV Research Bot

**Goal:** Find non-competing authorities serving our target market for partnership outreach.

**Flow:**
1. Trigger: weekly cron (Mon 9am) OR manual webhook with niche keyword
2. n8n calls Perplexity with multi-angle search prompts (podcast hosts, newsletter writers, course creators, community builders in target niche)
3. Extract per prospect: Name, Email, Social Links, audience size estimate, current offers
4. Dedupe against existing `JV_Targets` tab by domain + name
5. Append to `JV_Targets` tab with `status=jv_research_complete`
6. Discord summary: "JV batch: N new prospects added"

**Inputs:** niche keyword (manual) or stored config (cron)
**Outputs:** Rows in `JV_Targets` tab: Name, Email, Social_Links, Audience_Summary, Current_Offers, Source_URL, status, created_at

---

## Pipeline 3 — Terminator Loom Auto-Recorder (ScreenFlow-driven)

**Goal:** Auto-record customized prospect videos using a master MP3 pitch.

### Service structure

```
terminator-loom-recorder/
├── recorder.py              # main orchestrator (Playwright)
├── screenflow/              # bundled local copy of ScreenFlow
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   └── sw.js
├── assets/
│   ├── master_pitch.mp3
│   └── profile_overlay.png
├── output/                  # mp4s land here before upload
├── config.yaml              # paths, Sheets ID, Drive folder ID, MP3 duration
├── requirements.txt
└── README.md
```

Recorder spins up an internal HTTP server (Python `http.server`) on a free port, serves bundled ScreenFlow at `http://localhost:<port>`. Playwright Chromium points at it. **Zero external dependency** for the recorder UI.

### Playwright launch flags

```
--auto-select-tab-capture-source-by-title=Prospect-<slug>
--enable-features=AutoSelectTabCaptureSourceByTitle
--use-fake-ui-for-media-stream
--autoplay-policy=no-user-gesture-required
```

Plus `chromium.launch_persistent_context()` so ScreenFlow's IndexedDB survives between prospects in the same run.

### Per-prospect flow

1. Read row from `Terminator_Loom` tab where `status=ready_for_video`
2. Compute slug from First + Last name (e.g. `john-smith`)
3. Open ScreenFlow tab at `http://localhost:<port>`
4. DOM-set via Playwright:
   - mic toggle: OFF
   - system audio toggle: ON
   - filename prefix: `[First]_[Last]`
   - quality: 1080p
   - auto-stop timer: `MP3_duration_seconds + 2` (buffer)
   - countdown: OFF
5. Open prospect URL in new tab, set `document.title = "Prospect-<slug>"` via `page.evaluate()`, then `prospect_page.bring_to_front()` so it's the foreground tab
6. **Without switching focus**, click ScreenFlow's record button via JS evaluation:
   ```python
   await screenflow_page.evaluate("() => document.querySelector('#btn-record').click()")
   ```
   getDisplayMedia auto-accepts the foreground tab (Prospect) via the `--use-fake-ui-for-media-stream` flag. No native picker. (Validated in spike: PASS.)
7. The prospect tab is already foreground (set in step 5). Inject:
   ```js
   const audio = new Audio('http://localhost:<port>/assets/master_pitch.mp3');
   audio.play();
   ```
   (Captured by getDisplayMedia because tab audio routes through the tab capture)
8. Scroll prospect page:
   - Immediate scroll down to ~60% within first 1.5s (proves customization in GIF preview)
   - Scroll back to top by 3s
   - Slow continuous scroll through page for remainder of MP3
9. Auto-stop fires when timer expires
10. Switch to ScreenFlow library tab, click download on newest recording
11. Playwright catches download via `page.expect_download()`, saves to `output/{First}_{Last}.webm` (or .mp4 if browser produced it)
12. FFmpeg post-process — apply circular mask to profile pic, overlay bottom-left, ensure MP4 container:

    **Static PNG variant (v1 default):**
    ```
    ffmpeg -i input.webm -i assets/profile_overlay.png \
      -filter_complex "[1:v]scale=120:120,format=rgba,\
        geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(hypot(X-60,Y-60),60),255,0)'[circle];\
        [0:v][circle]overlay=20:H-h-20" \
      -c:v libx264 -c:a aac -pix_fmt yuv420p \
      output/{First}_{Last}.mp4
    ```
    The `geq` expression sets alpha=255 inside a 60px-radius circle and alpha=0 outside, producing the Loom-style circular camera bubble.

    **Animated GIF variant (opt-in via config flag):**
    ```
    ffmpeg -i input.webm -stream_loop -1 -i assets/profile_overlay.gif \
      -filter_complex "[1:v]scale=120:120,format=rgba,\
        geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(hypot(X-60,Y-60),60),255,0)'[circle];\
        [0:v][circle]overlay=20:H-h-20:shortest=1" \
      -c:v libx264 -c:a aac -pix_fmt yuv420p \
      output/{First}_{Last}.mp4
    ```
    `-stream_loop -1` loops the GIF; `shortest=1` ensures output ends with the screen recording, not the looped GIF.
13. Upload to designated Drive folder via Google Drive API
14. Update Sheet row: `video_drive_link`, `status=video_ready`, `recorded_at`
15. Sleep `random.uniform(3, 8)` before next prospect
16. Discord ping when batch complete

### Critical technical requirements

- Mic MUTED, system audio captured — handled by ScreenFlow's independent toggles
- Static profile picture overlay — FFmpeg `-filter_complex` post-process with **circular alpha mask** (mimics Loom's default camera bubble)
- Profile pic position: bottom-left corner (Loom default camera layout)
- Profile pic source: professional headshot per EasyGrow spec, NOT a logo (`assets/profile_overlay.png` or `.gif`)
- Optional: animated GIF overlay supported via config flag (alternating face/logo or any animation)
- Scroll motion MUST be visible in first 2 seconds (for GIF preview in email)
- File naming exactly `[First Name]_[Last Name].mp4` — no timestamp, no slug
- MP3 plays from the prospect tab (not ScreenFlow tab) so it's captured by `getDisplayMedia`
- MP3 file path is **config-driven** (`config.yaml`) — operator can hot-swap pitch without code change
- Recorder must **auto-detect MP3 duration** at startup (use `ffprobe` or `mutagen`) and warn if outside 60–120s range (EasyGrow spec: pitch must be 1–2 minutes)
- Auto-stop timer = detected MP3 duration + 2s buffer (no hardcoded duration)

### Pre-build spike (required before Claude Code session)

Validate `--auto-select-tab-capture-source-by-title` works in Playwright's bundled Chromium with ScreenFlow's `getDisplayMedia` call. **20-minute test:** launch Playwright with the flag, open ScreenFlow + a test tab titled "Prospect-test", click Record, confirm no picker appears and the right tab is captured. If it fails, fallback is `--use-fake-ui-for-media-stream` which auto-accepts but may pick wrong source — we'd need to validate it picks the active tab.

---

## Pipeline 4 — Facebook Group Inbound CRM Router

**Goal:** Instantly capture warm inbound leads from FB Group entry questions.

**Flow:**
1. Admin (Jon/setter) navigates to FB Group's Pending Member Requests in normal browser session
2. Chrome extension surfaces a "Capture pending requests" button
3. On click: extension reads visible pending members from DOM
4. Extracts per member: Name, Profile URL, answers to 3 entry questions:
   - Q1: "Where are you currently at in your business?" (current revenue)
   - Q2: "Where do you want to be with your business in the next 12 months?" (goals)
   - Q3: "Would you like me to reach out to discuss how we may be able to help you with that?" (DM permission — Option A locked)
5. Extension POSTs structured JSON to n8n webhook with rate-limited batching
6. n8n writes rows to `Inbound` tab with `status=warm_inbound`, `captured_at`
7. Discord ping immediately — **differentiated by Q3 value:**
   - Q3=Yes → `🔥 HOT: DM permission granted — {Name}` (operator drops Calendly via Direct Intent script)
   - Q3=No/empty → `Warm inbound: {Name}` (operator uses standard nurture flow)
8. Admin manually approves member + sends branded photo + 20s voice note via Messenger (manual, NOT automated)

**Inputs:** FB Group pending-members DOM (read via extension)
**Outputs:** Rows in `Inbound` tab: Name, Profile_URL, Q1_Revenue_Goal, Q2_Email, Q3_*, status, captured_at

**Constraints:**
- Extension is READ-ONLY on the DOM — no auto-approve, no auto-message
- Operator triggers manually (no background polling)
- All scraping uses `time.sleep(random.uniform(3, 8))` if any iteration happens

---

## Google Sheets schema

**One Sheet, four tabs.** No master tab — pipelines are independent.

### Tab: `Loomless`
| Col | Type |
|---|---|
| Company_Name | string |
| Owner_Full_Name | string |
| First_Name | string |
| Email | string |
| Website | string |
| Research_Summary | string (Perplexity output) |
| Personalized_First_Line | string (Claude output) |
| status | enum: `pending` \| `enriched` \| `ready_for_review` \| `sent` \| `dead` |
| created_at | timestamp |

### Tab: `JV_Targets`
| Col | Type |
|---|---|
| Name | string |
| Email | string |
| Social_Links | string (JSON or comma-sep) |
| Audience_Summary | string |
| Current_Offers | string |
| Source_URL | string |
| status | enum: `jv_research_complete` \| `contacted` \| `partnered` \| `dead` |
| created_at | timestamp |

### Tab: `Terminator_Loom`
| Col | Type |
|---|---|
| First_Name | string |
| Last_Name | string |
| Website | string |
| status | enum: `ready_for_video` \| `recording` \| `video_ready` \| `sent` \| `failed` |
| video_drive_link | string |
| recorded_at | timestamp |
| error_log | string |

### Tab: `Inbound`
| Col | Type |
|---|---|
| Name | string |
| Profile_URL | string |
| Q1_Current_Revenue | string ("Where are you currently at in your business?") |
| Q2_12_Month_Goal | string ("Where do you want to be with your business in the next 12 months?") |
| Q3_DM_Permission | string ("Yes"/"No"/raw — "Would you like me to reach out to discuss how we may be able to help you with that?") |
| status | enum: `warm_inbound` \| `welcomed` \| `nurturing` \| `converted` \| `dead` |
| operator_action | enum: `direct_intent_calendly` (if Q3=Yes) \| `standard_nurture` (otherwise) — set by n8n on insert |
| captured_at | timestamp |

---

## v0 setup tasks (Jon — parallel to dev work, blocking Pipeline 3 final validation only)

These are Jon's prep tasks. None block dev from STARTING any pipeline (placeholders work for build). All must be done before Pipeline 3 can be acceptance-tested with real outputs.

| # | Task | Blocks | Notes |
|---|---|---|---|
| 1 | **Record master MP3 pitch** | Pipeline 3 acceptance test | EasyGrow spec: 1–2 min, intro/offer/risk-reversal/CTA framework. Record 3 variants, pick best. Place in designated Drive folder + sync to local `assets/master_pitch.mp3` for recorder |
| 2 | **Provide profile pic headshot** | Pipeline 3 acceptance test | Professional headshot, NOT logo. 1024x1024 square PNG. Midjourney prompt available in EasyGrow if needed. Place at `assets/profile_overlay.png` |
| 3 | (Optional) Provide animated GIF variant | None — opt-in feature | Per EasyGrow course: looping GIF can boost video preview view rate vs static image. Place at `assets/profile_overlay.gif` and flip config flag |
| 4 | **Configure FB Group Q3 in Facebook admin** | Pipeline 4 live data | Set Q3 to: "Would you like me to reach out to discuss how we may be able to help you with that?" — must match what extension parses |

Dev uses placeholders (any 90-second mp3, any square headshot) during build. Swap real assets in at end for acceptance test.

---

## Build order

0. ~~**SPIKE: validate `--auto-select-tab-capture-source-by-title` flag** with Playwright + ScreenFlow~~ ✅ **DONE.** Picker bypass confirmed. Tab selection driven by foreground focus, not title-match; Pipeline 3 will click ScreenFlow's record button via Playwright JS evaluation while keeping Prospect tab in foreground.
1. ~~**Sheets schema + n8n base workflow scaffolding** — foundation~~ ✅ **DONE** (Build Spec #1, merged to main).
2. ~~**Loomless pipeline** — highest revenue impact, validates Perplexity + Claude prompts~~ ✅ **DONE** (Build Spec #2, merged to main `fa63f00`, 2026-07-05). Mock-validated: Smoke 1/2 + 4 failure modes + 100-lead run all green ($0); prompts UNTUNED until BS#6. Canonical source = n8n UI export; see `docs/MIGRATION_NOTE.md`.
3. **JV Research Bot** — reuses Loomless's Perplexity integration ← **NEXT**
4. **FB Group Chrome extension + webhook** — narrow scope, ships fast
5. **Terminator Loom recorder** — most complex, dedicated Claude Code session, depends on spike #0
6. **Handoff to company server machine** — package + migrate the full stack (n8n workflows, credentials shape, recorder service, docker compose, docs) to the company server. Uses the `handoff-package` skill. Produces a `HANDOFF.md` runbook that a fresh operator can follow to bring the whole system online. **Additionally (per Decision #12):** provision real credentials on the target machine (Anthropic, Perplexity, Google Service Account, Discord webhook, Chrome extension install, master MP3 + profile pic assets), run one real batch per pipeline as the acceptance test, and complete prompt tuning against real API responses.

Each step gets its own Claude Code session with this doc + the step's spec section + the Sheets schema. Don't one-shot all four.

---

## Per-pipeline acceptance criteria

- **Loomless:** Process a 100-lead CSV end-to-end. All rows in `Loomless` tab with `Personalized_First_Line` populated (or `[NO_CONTEXT]` flag). Discord summary fires. Zero manual intervention from CSV drop to ready_for_review.
- **JV Bot:** Single cron run produces ≥20 deduped JV prospects with audience data in `JV_Targets` tab.
- **Terminator Loom:** Given 10 prospect URLs, produce 10 mp4 files named `[First]_[Last].mp4` with: audible pitch playing throughout, visible scroll in first 2 seconds, profile pic overlay with **circular mask** anchored to **bottom-left** corner (Loom camera style), real master MP3 from v0 setup. All uploaded to Drive, all CRM rows updated with link.
- **FB Router:** Extension click captures all visible pending members from DOM, posts to webhook, lands in `Inbound` tab within 5s. Read-only confirmed (no DOM mutations).

---

## Risks

- ~~Auto-tab-select flag behavior~~ ✅ **Validated by spike (Jun 26):** picker is bypassed; tab selection is foreground-based (not title-match). Implementation pattern locked in Pipeline 3 spec.
- **FB extension detection:** Even read-only DOM scraping carries minor risk. Keep zero automated DOM mutations; operator-triggered only; never run in background.
- **Perplexity quota:** Two pipelines hit it. At 100 Loomless leads/day + 20 JV/week = ~3000/month. Verify Pro tier covers this.
- **Sheets at scale:** 100/day = 3000/month per tab. Fine for v1. At 400/day = 12000/month, may need archive rotation or migration to Supabase. Document threshold.
- **Discord notification fatigue:** Four pipelines pinging means we need a digest mode or a dedicated channel per pipeline. Plan: one `#ops-61-feed` channel, four message threads.
- **Profile pic overlay positioning:** FFmpeg overlay needs to handle different screen recordings (laptop vs desktop resolution). Test on Rinoah's actual recording resolution; consider relative positioning (`overlay=10:H-h-10`).
- **MP3 autoplay in injected audio element:** Chromium autoplay policy may block. Mitigated by `--autoplay-policy=no-user-gesture-required` launch flag.

### Risks no longer applicable (notable wins from ScreenFlow integration)

- ~~OS-level audio loopback setup (PulseAudio/BlackHole/VB-Cable)~~ — eliminated by `getDisplayMedia` tab audio capture
- ~~OBS scene management for profile pic overlay~~ — eliminated by FFmpeg post-process
- ~~Per-OS audio device validation~~ — eliminated; recorder is now OS-agnostic browser-driven
- ~~MP4 transcoding from raw screen capture~~ — ScreenFlow outputs MP4 natively on Chromium where available

---

## Out of scope (explicit)

- Automated email send (Loomless emails sent manually)
- Automated Loom/DM delivery (manual)
- FB Group member approval/rejection/messaging (manual — operator sends branded photo + voice note in Messenger)
- Reply/inbox handling
- Multi-tenant
- Loomless second-line, full-body, or follow-up sequences (v1 = first line only)
- Webcam capture for Terminator Loom (replaced by static profile pic via FFmpeg)
- Forking / modifying ScreenFlow (kept stable + reusable as internal tool)

---

## Reference

- NotebookLM: https://notebooklm.google.com/notebook/b80416ff-1023-4b63-9fda-033032bac504 (jonc@fascinatecopy.com)
- Linear: OPS-61
- Source doc: EasyGrow client acquisition program (Developer Handoff)
- ScreenFlow source: bundled with recorder service (originally hosted at facinatecopy-screenflow.netlify.app)
