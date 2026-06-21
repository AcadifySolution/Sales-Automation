# NEXUS Sales Engine — System Guide
### Automated B2B Lead Enrichment, CRM Sync, Email Outreach & Social Posting
**Designed for:** White-label resourcing model targeting US startups/agencies at Indian pricing.

---

## 📁 Organized Folder Structure

We have simplified the project directory to keep the root level clean and dashboard-friendly:

```
Sales Automation/
├── run.py                 ← 🚀 Master Runner (All commands start here)
├── .env                   ← 🔐 Credentials Database (The only file you edit)
├── requirements.txt       ← 📦 Python Packages List
├── README.md              ← 📖 Technical Readme
├── NEXUS_SYSTEM_GUIDE.md  ← 📖 Business & Flow Guide (This file)
│
├── engine/                ← ⚙️ Core Modules (No need to edit)
│   ├── lead_scraper.py      - Scrapes startup leads (HN, YC, ProductHunt)
│   ├── pipeline.py          - Claude personalization + HubSpot sync + SMTP email
│   ├── social_manager.py    - Creates and publishes LinkedIn + FB posts
│   └── followup_engine.py   - Automated 5-touch drip follow-up emails
│
├── data/                  ← 📊 Data Sheets (Check here for results)
│   ├── leads.csv            - Scraped and enriched target prospects
│   ├── pipeline_report.csv  - Initial cold email delivery reports
│   ├── content_calendar.csv - Generated 30-day social posting calendar
│   └── followup_tracker.csv - Day-by-day followup logs
│
├── logs/                  ← 📝 Logs (For troubleshooting)
│   ├── scraper.log
│   ├── pipeline.log
│   ├── social.log
│   └── followup.log
│
└── content/               ← 📝 Content Output
    ├── clutch_profile.txt       - Clutch profile descriptions
    └── clutch_review_requests.txt - Email templates for client reviews
```

---

## 🔄 How the Data Flows

When you run the master orchestration script, data flows dynamically between modules:

```
  Step 1: Discover               Step 2: Outreach              Step 3: Social               Step 4: Follow-up
 ┌────────────────┐             ┌────────────────┐            ┌────────────────┐           ┌────────────────┐
 │  lead_scraper  │             │    pipeline    │            │ social_manager │           │followup_engine │
 └───────┬────────┘             └───────┬────────┘            └───────┬────────┘           └───────┬────────┘
         │                              │                             │                            │
   Scrapes US startups            Uses Claude to                Generates 30-day             Checks tracker sheet
   hiring online.                 personalize emails.           social calendar.             for active leads.
         │                              │                             │                            │
   Scores ICP fit                 Syncs contact details         Publishes today's            Auto-sends next drip
   on 0-100 scale.                to HubSpot CRM.               scheduled posts.             if Day 3/7/10/14
         │                              │                             │                            │
         ▼                              ▼                             ▼                            ▼
  data/leads.csv          data/pipeline_report.csv        data/content_calendar.csv    data/followup_tracker.csv
```

---

## 🚀 How to Run the System

All tasks are managed via the master runner `run.py` from the root folder.

### 1. Daily Production Run
Execute all steps (Scrape → Email Outreach → Social Posting → Drip Followups):
```bash
python3 run.py
```

### 2. Run Specific Workflows
If you want to run only one step of the pipeline:
* **Lead Discovery Only:**
  ```bash
  python3 run.py --scrape-only
  ```
* **Initial Cold Emails Only:** (uses prospects already in `data/leads.csv`)
  ```bash
  python3 run.py --pipeline-only
  ```
* **Social Posting Only:** (posts today's scheduled content)
  ```bash
  python3 run.py --social-only
  ```
* **Follow-up Drips Only:** (sends scheduled follow-ups to active leads)
  ```bash
  python3 run.py --followup-only
  ```
* **Dry Run Preview:** (safe mode — prints outputs without sending emails or posting to APIs)
  ```bash
  python3 run.py --dry-run
  ```

---

## 🛠️ Built-in Robustness & Fail-Safes

To ensure that the system runs smoothly without technical crashes, several fail-safes are integrated directly:

### 1. HubSpot Sync Fallback Retry
* **The Problem:** Standard HubSpot accounts do not have the custom field `ai_personalized_pitch`. A standard integration would crash the sync.
* **The Fail-safe:** If the pipeline detects that the custom field doesn't exist, it prints instructions on how to create it, strips it from the payload, and automatically retries. The contact is successfully saved to your CRM on standard fields (First Name, Last Name, Email, Company, Job Title) rather than failing.

### 2. Case-Insensitive Header Normalization
* **The Problem:** Manual edits to `leads.csv` can lead to key changes (e.g. `first_name` or `email address` instead of `First Name` or `Email`), crashing typical CSV parsers.
* **The Fail-safe:** The loaders dynamically map common synonym variations to standard fields, meaning the pipeline handles manual formatting changes safely.

### 3. Safe ICP Sorting
* **The Problem:** Leads from static lists or fallbacks might have blank or invalid scores, causing sort exceptions.
* **The Fail-safe:** Safe-casting guarantees blank scores default to `0` and sorts them without errors.

### 4. Exponential Backoff & Retry
* All Claude API calls, SMTP connections, and Graph API requests are structured with a 3× retry loop and exponential backoff to handle transient network hiccups cleanly.
