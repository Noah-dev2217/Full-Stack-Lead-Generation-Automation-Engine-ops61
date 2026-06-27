# Developer Handoff: Full-Stack Lead Generation & Automation Engine

> Source: provided by Jon, derived from the EasyGrow client acquisition program. This is the canonical spec OPS-61 is built against. Where this and `OPS-61_PLAN.md` differ, the plan reflects the resolved interpretation — see decisions table in the plan for any divergence and the reasoning.

---

## 1. Project Overview

You are tasked with building a suite of internal automations to scale our outbound and inbound lead generation efforts. We are implementing strategies from the "EasyGrow" client acquisition program.

**CRITICAL DIRECTIVE:** Our core philosophy is to automate the heavy lifting of research, data processing, copy generation, and video asset creation. We absolutely DO NOT automate the actual sending of emails or direct messages. Automating the delivery process will ruin our domain deliverability and trigger spam filters and platform bans. Your automations must strictly stop at logging the created assets and data into our CRM (Google Sheets).

## 2. Tech Stack

- **Workflow Engine:** Self-hosted n8n
- **LLM APIs:** Claude Max API (for copywriting), Perplexity Pro API (for live internet research)
- **Browser/Local Automation:** Python (Selenium/Playwright, PyAutoGUI) or TaskMagic, OBS Studio / FFmpeg (for local video recording)
- **Database/CRM:** Google Workspace (Google Sheets)

## 3. Automation Modules to Build

### Module A: The Loomless AI Personalization Pipeline (n8n + Perplexity + Claude)

**Objective:** Automate the research and copy generation for high-volume text-based cold emails (up to 400/day).

**Input:** A raw CSV containing scraped lead data (Company Name, Owner Full Name, First Name, Email, Website).

**Process:**
1. n8n reads the CSV row by row.
2. n8n triggers the Perplexity API to search the web/LinkedIn for recent achievements, company news, or personal context regarding the lead.
3. n8n passes the summarized research to the Claude Max API.
4. Claude generates a hyper-personalized first line.

**Copywriting Rules for Claude:** The first line must sound human, casual, and highly relevant. Examples of successful first lines:
- *"Saw you recently posted about your 40% close rate in December. Congrats!"*
- *"Noticed on LinkedIn you're based in Ottawa. If we connect, I'd be happy to buy you lunch at Riviera!"*

**Output:** n8n updates the Google Sheet CRM with a new column: `Personalized_First_Line`.

### Module B: Joint Venture (JV) Research Bot (n8n + Perplexity)

**Objective:** Identify non-competing businesses that share our ideal client profile for partnership outreach.

**Input:** Scheduled n8n cron job or webhook providing a niche/industry keyword.

**Process:**
1. Use Perplexity API to identify non-competing authorities or businesses serving the same target audience.
2. Scrape and extract their key contact information (Email, Name, Social Links) and a brief summary of their audience size and current offers.

**Output:** Append this data directly to a dedicated "JV Targets" tab in our Google Sheets CRM.

### Module C: Terminator Loom Auto-Recorder (Python/Browser Automation + FFmpeg/OBS)

**Objective:** Simulate a manual Loom recording over a prospect's website using a pre-recorded master MP3 pitch.

**Input:** Google Sheet containing Prospect First Name, Last Name, and Website URL.

**Process:**
1. Script opens the prospect's website URL in a browser.
2. Script ensures the recording microphone is muted, but "use system audio" is ON to capture the MP3.
3. Instead of a live webcam feed, the script should display a static profile picture in the bottom left corner to avoid lip-sync issues.
4. Script starts the screen recording and simultaneously plays the master MP3 audio file.
5. **CRITICAL:** The script must immediately scroll down the website and back up as soon as the recording starts. This eliminates the suspicion that the video is pre-recorded and ensures movement is caught in the email's GIF preview.
6. Stop recording when the MP3 finishes.

**Output:** Save the video file locally named strictly as `[First Name]_[Last Name].mp4` (or `.webm`) and upload it to a designated Google Drive folder. Update the CRM with the file link.

### Module D: Facebook Group Inbound CRM Router (Local Scraper/n8n)

**Objective:** Capture warm inbound leads requesting to join our free Facebook group funnel.

**Process:**
1. Write a safe, rate-limited local browser script to scrape the "Pending Member Requests" tab in our Facebook Group.
2. Extract the member's Name, Profile URL, and their answers to the 3 mandatory entry questions (e.g., Revenue goals, Email address).
3. Push this data via webhook to n8n.
4. n8n logs the lead into the "Inbound" tab of the Google Sheet CRM.

**Constraint:** The script should not automatically accept the user or message them. Human setters must manually approve the request, send a branded photo, and record a live 20-second welcome voice note via Messenger.

## 4. Deliverability & Safety Safeguards (Strict Rules)

- **No Automated Sending:** You will not write any scripts that interface with SMTP protocols, Gmail APIs, or Social Media messaging APIs to send outgoing messages. All sending is handled by human operators to maintain a "perfectly human and normal" behavior profile.
- **Rate Limiting:** Any web scraping (e.g., Facebook group scraping) must include randomized human-like delays (e.g., `time.sleep(random.uniform(3, 8))`) to prevent platform bans.

---

## Supplementary clarifications (from Jon, post-handoff)

### FB Group Q1, Q2, Q3 (exact wording from EasyGrow / Charlie)

- **Q1:** "Where are you currently at in your business?" (current revenue)
- **Q2:** "Where do you want to be with your business in the next 12 months?" (12-month goal)
- **Q3 (LOCKED — Option A, DM permission):** "Would you like me to reach out to discuss how we may be able to help you with that?"

When Q3=Yes lands in the Sheet, operator action is unambiguous: skip warm-up, use Direct Intent reply scripts, drop Calendly link.

### Master MP3 pitch (v0 setup task — Jon)

- **Duration:** strictly 1–2 minutes, no longer
- **Framework:** intro, offer, risk reversal, call-to-action (per Charlie / EasyGrow)
- **Process:** record 3 variants, pick best, upload to designated Drive folder
- **Dev usage:** script references a config-driven path; can hot-swap MP3 without code change

### Profile pic overlay (v0 setup task — Jon)

- **Type:** professional headshot of Jon's face, NOT a company logo
- **Source format:** 1024x1024 square PNG (or animated GIF for v1.5 experimentation)
- **Treatment:** circular alpha mask applied via FFmpeg (mimics Loom's default camera bubble)
- **Position:** bottom-left corner
- **AI generation option:** Midjourney with prompt `/Imagine: NAME, NICHE, GENDER, 30 years old, professional headshot, solid background, portrait`
- **Bonus:** looping GIF variant can boost email video preview view rate
