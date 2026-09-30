# NEXUS Sales Automation

> AI-assisted B2B sales automation for lead discovery, lead enrichment, personalized outreach, CRM synchronization, follow-ups, and social content workflows.

[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)](requirements.txt)
[![Flask](https://img.shields.io/badge/Flask-dashboard-000000.svg)](app.py)
[![AI](https://img.shields.io/badge/AI-Anthropic-compatible-6B4EFF.svg)](engine/pipeline.py)
[![CRM](https://img.shields.io/badge/CRM-HubSpot-FF7A59.svg)](engine/pipeline.py)

NEXUS is a Python sales automation workspace for B2B prospecting and outreach. It combines lead discovery, enrichment, ICP scoring, AI-assisted email personalization, HubSpot synchronization, follow-up scheduling, and social publishing behind a single master runner and a local Flask dashboard.

## Features

| Capability | Purpose |
| --- | --- |
| Lead discovery | Collect prospects from supported public sources and startup ecosystems |
| Lead enrichment | Normalize prospect fields and enrich contact information |
| ICP scoring | Rank prospects against configurable ideal-customer criteria |
| AI personalization | Generate prospect-specific outreach using an LLM provider |
| CRM sync | Push qualified contacts and enrichment fields into HubSpot |
| Email outreach | Send initial outreach through SMTP |
| Follow-up automation | Manage scheduled follow-up touches |
| Social automation | Generate and publish LinkedIn/Facebook content |
| Dashboard | Inspect leads, KPIs, configuration, execution status, calendar data, and logs |
| Dry-run mode | Preview automation without sending outreach or publishing posts |

## Architecture

```text
                         ┌─────────────────────┐
                         │      run.py         │
                         │    Master Runner    │
                         └──────────┬──────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
 ┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐
 │ Lead Discovery  │      │ Outreach Pipeline│      │ Social / Followup│
 │ lead_scraper.py │      │    pipeline.py   │      │      engines      │
 └────────┬────────┘      └─────────┬────────┘      └────────┬─────────┘
          │                         │                        │
          ▼                         ▼                        ▼
   data/leads.csv          AI + HubSpot + SMTP      calendar / tracker
          │                         │                        │
          └─────────────────────────┼────────────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │    Flask Dashboard  │
                         │       app.py        │
                         └─────────────────────┘
```

## Project structure

```text
.
├── app.py
├── run.py
├── engine/
│   ├── followup_engine.py
│   ├── lead_scraper.py
│   ├── pipeline.py
│   └── social_manager.py
├── templates/
│   └── index.html
├── data/
│   └── leads.csv
├── NEXUS_SYSTEM_GUIDE.md
├── requirements.txt
├── pyproject.toml
└── README.md
```

Runtime-generated files such as logs, calendars, trackers, and reports should remain local and are excluded from version control.

## Quick start

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a local `.env` from the example template:

```bash
cp .env.example .env
```

Never commit real API keys, passwords, access tokens, or SMTP credentials.

### 3. Validate configuration

Run a safe preview before any external action:

```bash
python3 run.py --dry-run
```

### 4. Start the dashboard

```bash
python3 app.py
```

Open the local Flask dashboard in your browser.

## Automation commands

```bash
# Full workflow
python3 run.py

# Individual stages
python3 run.py --scrape-only
python3 run.py --pipeline-only
python3 run.py --social-only
python3 run.py --followup-only

# Social setup
python3 run.py --generate
python3 run.py --clutch
python3 run.py --schedule

# Safe preview
python3 run.py --dry-run
```

Before using commands that send email, update CRM records, or publish social content, verify credentials, recipients, rate limits, and campaign content.

## Environment configuration

The system uses environment variables for integration settings. The exact variables are documented in [.env.example](.env.example).

Typical integrations include:

- Anthropic API for AI-assisted generation
- HubSpot API for CRM synchronization
- SMTP/Gmail for email delivery
- Hunter.io for email enrichment
- LinkedIn and Facebook APIs for social publishing
- Product Hunt and startup/public-source discovery

## Security model

This repository is intended to keep credentials out of source control and avoid exposing them through the dashboard.

Security controls include:

- `.env` exclusion through `.gitignore`
- masked sensitive configuration values in the dashboard
- dry-run support for operational testing
- explicit integration configuration
- exception handling around external API calls

Treat generated prospect and outreach data as business data. Apply appropriate access controls, retention practices, consent requirements, and provider terms before production use.

## Operational safeguards

Sales automation can create external side effects. A production deployment should additionally establish:

- sending limits and rate limits
- suppression / unsubscribe handling
- duplicate-lead protection
- campaign approval before publishing
- audit trails for externally visible actions
- retry and idempotency controls
- secrets management outside developer workstations
- monitoring and alerting
- backup and recovery procedures

## Responsible AI usage

AI-generated outreach should be reviewed before production use. The model should assist with personalization rather than inventing customer facts, guarantees, testimonials, or claims.

For AI-assisted sales workflows:

1. Ground personalization in verified lead data.
2. Do not fabricate company details or customer relationships.
3. Review generated content before sending.
4. Keep sensitive data out of prompts unless explicitly required and appropriately protected.
5. Maintain provider-specific policies and limits.
6. Record important failures and corrections.

## Documentation

- [NEXUS System Guide](NEXUS_SYSTEM_GUIDE.md) — detailed workflow and architecture notes
- [Environment template](.env.example) — required configuration shape
- [Security Policy](SECURITY.md) — security reporting and handling
- [Contributing Guide](CONTRIBUTING.md) — development workflow

## Search topics

**sales automation, B2B sales automation, AI sales automation, lead generation, lead scraping, lead enrichment, sales outreach, cold email automation, AI email personalization, CRM automation, HubSpot integration, follow-up automation, social media automation, Python sales tools, Flask sales dashboard, startup lead generation, AI-assisted sales, sales pipeline automation.**

## License

See [LICENSE](LICENSE) for the applicable licensing terms.

---

NEXUS Sales Automation is maintained by Acadify Solution as an evolving automation project. Evaluate integrations, compliance requirements, deliverability, and provider policies before production deployment.
