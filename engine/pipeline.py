#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  NEXUS SALES PIPELINE  |  AI-Powered B2B Outreach Engine
  Built for: [Your Company Name] — Software Development & AI Data Solutions
  Author:    pipeline.py v2.0
  Strategy:  CEO-Level Outreach | Personalized at Scale | Zero Manual Work
================================================================================

  PIPELINE ARCHITECTURE:
  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
  │  leads.csv  │ →  │  Claude 3.5      │ →  │  HubSpot CRM    │ →  │  Gmail SMTP  │
  │  (8 fields) │    │  Sonnet Enricher │    │  Upsert Engine  │    │  Dispatcher  │
  └─────────────┘    └──────────────────┘    └─────────────────┘    └──────────────┘
                              ↓                        ↓                     ↓
                     [ai_personalized_pitch]  [Contact Created/Updated]  [Email Sent]
                                              ───────────────────────────────────────
                                                    Pipeline Run Report → report.csv
"""

import os
import sys
import time
import csv
import smtplib
import logging
import random
import re
from typing import Optional, Tuple, Any, List, Dict, cast
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Third-party (pip install python-dotenv anthropic hubspot-api-client pandas) ──
try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("❌  Missing: python-dotenv  →  Run: pip install python-dotenv")

try:
    import anthropic
except ImportError:
    sys.exit("❌  Missing: anthropic  →  Run: pip install anthropic")

try:
    from hubspot import HubSpot
    from hubspot.crm.contacts import SimplePublicObjectInputForCreate
    from hubspot.crm.contacts.exceptions import ApiException
except ImportError:
    sys.exit("❌  Missing: hubspot-api-client  →  Run: pip install hubspot-api-client")

try:
    import pandas as pd
except ImportError:
    sys.exit("❌  Missing: pandas  →  Run: pip install pandas")


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 0 — LOGGING SETUP
# ════════════════════════════════════════════════════════════════════════════════
ROOT = Path(__file__).parent.parent
(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "data").mkdir(exist_ok=True)

LOG_FILE = ROOT / "logs" / "pipeline.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("nexus-pipeline")


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — CONFIGURATION & CONSTANTS
# ════════════════════════════════════════════════════════════════════════════════

LEADS_FILE      = ROOT / "data" / "leads.csv"
REPORT_FILE     = ROOT / "data" / "pipeline_report.csv"
CLAUDE_MODEL    = "claude-3-5-sonnet-20241022"
MAX_TOKENS      = 200
RATE_LIMIT_WAIT = 2       # seconds between Claude calls (respect rate limits)
MAX_RETRIES     = 3       # max retries on transient errors
BACKOFF_BASE    = 2       # exponential backoff multiplier

# ── SMTP Config ──
SMTP_PROVIDERS = {
    "gmail": {
        "host": "smtp.gmail.com",
        "port": 587,
    },
    "outlook": {
        "host": "smtp.office365.com",
        "port": 587,
    },
}

# ── Company Identity (CEO Context) ──
COMPANY_NAME    = "YourCompany.ai"          # ← Replace with your brand
COMPANY_TAGLINE = "Custom AI Systems & Data Engineering"
SENDER_NAME     = "Founder, YourCompany.ai" # ← Replace with your name/title
CALENDLY_LINK   = "https://calendly.com/yourcompany/15min"  # ← Your link


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — ENVIRONMENT LOADER & GUARD
# ════════════════════════════════════════════════════════════════════════════════

def load_and_validate_env() -> dict:
    """
    Load .env and strictly validate that no placeholder values remain.
    Returns a clean dict of all required credentials.
    """
    env_path = ROOT / ".env"
    if not env_path.exists():
        sys.exit("❌  .env file not found. Create it in the same directory as pipeline.py")

    load_dotenv(env_path)

    required_keys = [
        "ANTHROPIC_API_KEY",
        "HUBSPOT_ACCESS_TOKEN",
        "SENDER_EMAIL",
        "EMAIL_APP_PASSWORD",
    ]

    credentials = {}
    placeholder_found = []

    for key in required_keys:
        value = os.getenv(key, "")
        if not value or "PLACEHOLDER" in value.upper():
            placeholder_found.append(key)
        else:
            credentials[key] = value

    if placeholder_found:
        print("\n" + "═" * 60)
        print("🚫  PIPELINE HALTED — CREDENTIALS NOT CONFIGURED")
        print("═" * 60)
        print("   The following keys still contain placeholder values:")
        for k in placeholder_found:
            print(f"   ✗  {k}")
        print("\n   📋 Action Required:")
        print("   Open .env and replace each PLACEHOLDER_DO_NOT_RUN")
        print("   with your actual API keys and credentials.")
        print("═" * 60 + "\n")
        sys.exit(1)

    log.info("✅  All credentials loaded and validated from .env")
    return credentials


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — LEADS LOADER
# ════════════════════════════════════════════════════════════════════════════════

def load_leads(filepath: Path) -> List[Dict[str, Any]]:
    """
    Load leads from CSV. Validates required columns exist.
    Skips rows with missing email addresses. Supports flexible column headers.
    """
    required_cols = {"First Name", "Email", "Company", "Job Title"}

    if not filepath.exists():
        sys.exit(f"❌  leads.csv not found at: {filepath}")

    df = pd.read_csv(filepath)
    df.columns = df.columns.str.strip()

    # Flexible case-insensitive header mapper
    col_mapping = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in ("first name", "firstname", "first_name"):
            col_mapping[col] = "First Name"
        elif col_lower in ("last name", "lastname", "last_name"):
            col_mapping[col] = "Last Name"
        elif col_lower in ("email", "email address", "email_address"):
            col_mapping[col] = "Email"
        elif col_lower in ("company", "company name", "company_name"):
            col_mapping[col] = "Company"
        elif col_lower in ("job title", "jobtitle", "job_title", "title"):
            col_mapping[col] = "Job Title"
        elif col_lower in ("industry", "sector"):
            col_mapping[col] = "Industry"
        elif col_lower in ("company size", "companysize", "company_size", "size"):
            col_mapping[col] = "Company Size"
        elif col_lower in ("location", "country", "city"):
            col_mapping[col] = "Location"
        elif col_lower in ("website", "url", "domain"):
            col_mapping[col] = "Website"
        elif col_lower in ("company type", "companytype", "company_type"):
            col_mapping[col] = "Company Type"
        elif col_lower in ("source", "lead_source"):
            col_mapping[col] = "Source"
        elif col_lower in ("icp score", "icpscore", "icp_score", "score"):
            col_mapping[col] = "ICP Score"
        elif col_lower in ("notes", "description", "details"):
            col_mapping[col] = "Notes"

    df = df.rename(columns=col_mapping)

    missing = required_cols - set(df.columns)
    if missing:
        sys.exit(f"❌  Missing required columns in leads.csv: {missing}")

    # Drop rows with no email
    before = len(df)
    filtered_df = df[df["Email"].notna() & (df["Email"].str.strip() != "")]
    skipped = before - len(filtered_df)
    if skipped > 0:
        log.warning(f"⚠️   Skipped {skipped} rows with missing email addresses")

    df_records = cast(pd.DataFrame, filtered_df)
    leads = cast(List[Dict[str, Any]], df_records.to_dict(orient="records"))
    log.info(f"📋  Loaded {len(leads)} valid leads from {filepath.name}")
    return leads


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — EMAIL VALIDATOR
# ════════════════════════════════════════════════════════════════════════════════

def is_valid_email(email: str) -> bool:
    """Basic RFC 5322 email format check."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — CLAUDE ENRICHMENT ENGINE
# ════════════════════════════════════════════════════════════════════════════════

def build_system_prompt() -> str:
    """
    CEO-level system prompt: We are a software dev + AI data company.
    Claude must write openers that feel like they came from a founder,
    not a sales bot.
    """
    return (
        "You are the founder of a boutique software development and AI data engineering firm. "
        "You write cold email openers that are razor-sharp, human, and hyper-relevant. "
        "Your firm builds: custom AI agents, data pipelines, automation systems, and SaaS products for B2B companies. "
        "Write exactly ONE sentence — the opening line of a cold email — for the given prospect. "
        "Rules: "
        "- Do NOT start with 'I hope', 'I wanted to', 'Congratulations', or any corporate opener. "
        "- Do NOT mention 'AI' or 'machine learning' explicitly unless the prospect is in that field. "
        "- Reference something specific about their role or company type organically. "
        "- Match the energy of someone who genuinely understands their world. "
        "- Output ONLY the one sentence. No subject line. No greeting. No explanation."
    )


def build_user_prompt(lead: dict) -> str:
    """
    Construct a rich prompt payload from lead fields.
    """
    industry  = lead.get("Industry", "technology")
    size      = lead.get("Company Size", "unknown size")
    return (
        f"Prospect: {lead['First Name']} {lead.get('Last Name', '')} | "
        f"Title: {lead['Job Title']} | "
        f"Company: {lead['Company']} | "
        f"Industry: {industry} | "
        f"Company Size: {size} employees"
    )


def call_claude_with_retry(client: anthropic.Anthropic, lead: dict) -> Optional[str]:
    """
    Call Claude API with exponential backoff retry logic.
    Returns the personalized pitch or None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                system=build_system_prompt(),
                messages=[
                    {"role": "user", "content": build_user_prompt(lead)}
                ],
            )
            block = response.content[0]
            pitch = getattr(block, "text", "").strip()
            log.info(f"   🤖  Claude pitch: \"{pitch}\"")
            return pitch

        except anthropic.RateLimitError:
            wait_time = BACKOFF_BASE ** attempt + random.uniform(0, 1)
            log.warning(f"   ⏳  Claude rate limit hit. Waiting {wait_time:.1f}s (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait_time)

        except anthropic.APIConnectionError as e:
            log.warning(f"   🔌  Claude connection error: {e}. Attempt {attempt}/{MAX_RETRIES}")
            time.sleep(BACKOFF_BASE ** attempt)

        except anthropic.APIStatusError as e:
            log.warning(f"   ⚠️   Claude API error {e.status_code}: {e.message}. Attempt {attempt}/{MAX_RETRIES}")
            if e.status_code in (400, 401, 403):
                break  # Non-retriable
            time.sleep(BACKOFF_BASE ** attempt)

        except Exception as e:
            log.warning(f"   ❌  Unexpected Claude error: {e}. Attempt {attempt}/{MAX_RETRIES}")
            time.sleep(BACKOFF_BASE ** attempt)

    log.error(f"   💀  Claude enrichment FAILED after {MAX_RETRIES} attempts for {lead.get('Email')}")
    return None


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — HUBSPOT CRM ENGINE
# ════════════════════════════════════════════════════════════════════════════════

def get_hubspot_contact_id(hs_client: HubSpot, email: str) -> Optional[str]:
    """
    Search HubSpot for a contact by email.
    Returns contact ID if found, else None.
    """
    try:
        from hubspot.crm.contacts import PublicObjectSearchRequest
        filter_group = {
            "filters": [
                {
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email,
                }
            ]
        }
        search_request = PublicObjectSearchRequest(
            filter_groups=[filter_group],
            properties=["email", "firstname", "lastname"],
            limit=1,
        )
        result = hs_client.crm.contacts.search_api.do_search(
            public_object_search_request=search_request
        )
        if getattr(result, "total", 0) > 0:
            return getattr(result, "results")[0].id
        return None

    except Exception as e:
        log.warning(f"   ⚠️   HubSpot search error for {email}: {e}")
        return None


def upsert_hubspot_contact(hs_client: HubSpot, lead: dict, pitch: str) -> Tuple[Optional[str], str]:
    """
    Create or update a HubSpot contact with lead data + AI pitch.
    Returns (contact_id, action) where action is 'created' or 'updated'.
    """
    properties = {
        "firstname":            str(lead.get("First Name", "")).strip(),
        "lastname":             str(lead.get("Last Name", "")).strip(),
        "email":                str(lead.get("Email", "")).strip(),
        "company":              str(lead.get("Company", "")).strip(),
        "jobtitle":             str(lead.get("Job Title", "")).strip(),
        "ai_personalized_pitch": pitch,
    }

    existing_id = get_hubspot_contact_id(hs_client, properties["email"])

    try:
        if existing_id:
            # ── UPDATE existing contact ──
            from hubspot.crm.contacts import SimplePublicObjectInput
            update_input = SimplePublicObjectInput(properties=properties)
            hs_client.crm.contacts.basic_api.update(
                contact_id=existing_id,
                simple_public_object_input=update_input
            )
            log.info(f"   🔄  HubSpot UPDATED  → ID: {existing_id}")
            return existing_id, "updated"
        else:
            # ── CREATE new contact ──
            create_input = SimplePublicObjectInputForCreate(properties=properties)
            result = hs_client.crm.contacts.basic_api.create(
                simple_public_object_input_for_create=create_input
            )
            created_id = getattr(result, "id", "")
            log.info(f"   ➕  HubSpot CREATED  → ID: {created_id}")
            return created_id, "created"

    except ApiException as e:
        err_msg = str(e.body) if hasattr(e, "body") else str(e)
        if "ai_personalized_pitch" in err_msg.lower():
            log.warning("   ⚠️   HubSpot Custom Property 'ai_personalized_pitch' does not exist in your CRM account.")
            log.warning("       ACTION REQUIRED: In HubSpot, go to Settings -> Properties -> Contacts,")
            log.warning("       and create a new custom Text property with name and label: 'ai_personalized_pitch'.")
            log.warning("       Retrying contact sync without the AI pitch field...")
            
            # Fallback properties list
            fallback_props = properties.copy()
            fallback_props.pop("ai_personalized_pitch", None)
            
            try:
                if existing_id:
                    from hubspot.crm.contacts import SimplePublicObjectInput
                    update_input = SimplePublicObjectInput(properties=fallback_props)
                    hs_client.crm.contacts.basic_api.update(
                        contact_id=existing_id,
                        simple_public_object_input=update_input
                    )
                    log.info(f"   🔄  HubSpot UPDATED (fallback without pitch)  → ID: {existing_id}")
                    return existing_id, "updated"
                else:
                    create_input = SimplePublicObjectInputForCreate(properties=fallback_props)
                    result = hs_client.crm.contacts.basic_api.create(
                        simple_public_object_input_for_create=create_input
                    )
                    created_id = getattr(result, "id", "")
                    log.info(f"   ➕  HubSpot CREATED (fallback without pitch)  → ID: {created_id}")
                    return created_id, "created"
            except Exception as retry_err:
                log.warning(f"   ❌  HubSpot fallback retry failed: {retry_err}")
                return None, "failed"

        log.warning(f"   ⚠️   HubSpot API exception for {properties['email']}: {e.reason}")
        return None, "failed"

    except Exception as e:
        log.warning(f"   ⚠️   HubSpot unexpected error for {properties['email']}: {e}")
        return None, "failed"


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — HTML EMAIL TEMPLATE (CEO BRAND VOICE)
# ════════════════════════════════════════════════════════════════════════════════

def build_html_email(first_name: str, pitch: str) -> str:
    """
    Build a premium, conversion-optimised HTML cold email.
    Designed to look personal, not like a mass blast.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>A quick thought, {first_name}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    body {{
      margin: 0; padding: 0;
      background-color: #f4f6f9;
      font-family: 'Inter', Arial, sans-serif;
      color: #1a1a2e;
    }}
    .wrapper {{
      max-width: 600px;
      margin: 40px auto;
      background: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    }}
    .header {{
      background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
      padding: 36px 40px 28px;
      text-align: left;
    }}
    .header .logo {{
      font-size: 20px;
      font-weight: 600;
      color: #ffffff;
      letter-spacing: -0.5px;
    }}
    .header .tagline {{
      font-size: 12px;
      color: #a78bfa;
      margin-top: 4px;
      text-transform: uppercase;
      letter-spacing: 1.2px;
    }}
    .body {{
      padding: 40px;
    }}
    .greeting {{
      font-size: 17px;
      font-weight: 500;
      color: #1a1a2e;
      margin-bottom: 16px;
    }}
    .opener {{
      font-size: 16px;
      line-height: 1.7;
      color: #374151;
      border-left: 3px solid #7c3aed;
      padding-left: 16px;
      margin: 20px 0;
      font-style: italic;
    }}
    .body-text {{
      font-size: 15px;
      line-height: 1.8;
      color: #4b5563;
      margin-bottom: 14px;
    }}
    .cta-block {{
      margin: 32px 0;
      text-align: center;
    }}
    .cta-btn {{
      display: inline-block;
      background: linear-gradient(135deg, #7c3aed, #4f46e5);
      color: #ffffff !important;
      text-decoration: none;
      padding: 14px 32px;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.3px;
    }}
    .divider {{
      border: none;
      border-top: 1px solid #f0f0f5;
      margin: 28px 0;
    }}
    .signature {{
      font-size: 14px;
      color: #6b7280;
      line-height: 1.6;
    }}
    .signature strong {{
      color: #1a1a2e;
      font-weight: 600;
    }}
    .footer {{
      background: #f9fafb;
      padding: 20px 40px;
      font-size: 12px;
      color: #9ca3af;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="logo">{COMPANY_NAME}</div>
      <div class="tagline">{COMPANY_TAGLINE}</div>
    </div>

    <div class="body">
      <div class="greeting">Hey {first_name},</div>

      <div class="opener">"{pitch}"</div>

      <p class="body-text">
        I run a small, focused team that builds <strong>custom AI systems and data 
        pipelines</strong> for companies that are serious about operational efficiency. 
        We've shipped everything from internal automation tools to production ML infrastructure 
        — typically in 4–8 weeks, not 6 months.
      </p>

      <p class="body-text">
        Not trying to sell you anything today. I just thought there might be a fit based 
        on what your team is building, and a quick 15-minute call might be worth it.
      </p>

      <div class="cta-block">
        <a href="{CALENDLY_LINK}" class="cta-btn">
          → Grab a 15-min slot
        </a>
      </div>

      <p class="body-text">
        Either way, happy to share some of our recent case studies if useful.
      </p>

      <hr class="divider" />

      <div class="signature">
        <strong>{SENDER_NAME}</strong><br/>
        {COMPANY_NAME} — {COMPANY_TAGLINE}<br/>
        <a href="{CALENDLY_LINK}" style="color:#7c3aed;">{CALENDLY_LINK}</a>
      </div>
    </div>

    <div class="footer">
      You received this because we believe there's a genuine fit. No tricks, no sequences.
      Just a founder reaching out directly.
    </div>
  </div>
</body>
</html>"""


def build_plain_email(first_name: str, pitch: str) -> str:
    """Plain-text fallback for email clients that block HTML."""
    return f"""Hey {first_name},

{pitch}

I run a small, focused team that builds custom AI systems and data pipelines for companies 
serious about operational efficiency. We ship in 4–8 weeks, not 6 months.

No pitch deck, no pressure — just a 15-min call to see if there's a fit.

Grab a slot: {CALENDLY_LINK}

— {SENDER_NAME}
{COMPANY_NAME} | {COMPANY_TAGLINE}
"""


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — SMTP EMAIL DISPATCHER
# ════════════════════════════════════════════════════════════════════════════════

def detect_smtp_provider(sender_email: str) -> dict:
    """Auto-detect SMTP settings from sender email domain."""
    domain = sender_email.split("@")[-1].lower()
    if "gmail" in domain:
        return SMTP_PROVIDERS["gmail"]
    elif "outlook" in domain or "hotmail" in domain or "live" in domain:
        return SMTP_PROVIDERS["outlook"]
    else:
        # Default to Gmail-compatible TLS
        log.warning(f"   ⚠️   Unknown email domain '{domain}' — defaulting to Gmail SMTP settings")
        return SMTP_PROVIDERS["gmail"]


def send_email(
    sender_email: str,
    app_password: str,
    recipient_email: str,
    first_name: str,
    pitch: str,
) -> bool:
    """
    Dispatch a styled HTML email with plain-text fallback.
    Returns True on success, False on failure.
    """
    subject = f"Quick thought on {first_name}'s roadmap"
    smtp_config = detect_smtp_provider(sender_email)

    msg = MIMEMultipart("alternative")
    msg["From"]    = f"{SENDER_NAME} <{sender_email}>"
    msg["To"]      = recipient_email
    msg["Subject"] = subject
    msg["Reply-To"] = sender_email

    # Attach both plain and HTML parts (HTML shown if supported)
    msg.attach(MIMEText(build_plain_email(first_name, pitch), "plain", "utf-8"))
    msg.attach(MIMEText(build_html_email(first_name, pitch),  "html",  "utf-8"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(sender_email, app_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())
                log.info(f"   📧  Email SENT → {recipient_email}")
                return True

        except smtplib.SMTPAuthenticationError:
            log.error("   🔐  SMTP Authentication FAILED. Check SENDER_EMAIL / EMAIL_APP_PASSWORD in .env")
            return False  # No point retrying auth errors

        except smtplib.SMTPRecipientsRefused:
            log.warning(f"   📵  SMTP: Recipient refused → {recipient_email}")
            return False

        except smtplib.SMTPConnectError as e:
            log.warning(f"   🔌  SMTP connection error: {e}. Attempt {attempt}/{MAX_RETRIES}")
            time.sleep(BACKOFF_BASE ** attempt)

        except smtplib.SMTPException as e:
            log.warning(f"   ⚠️   SMTP error: {e}. Attempt {attempt}/{MAX_RETRIES}")
            time.sleep(BACKOFF_BASE ** attempt)

        except Exception as e:
            log.warning(f"   ❌  Unexpected email error: {e}. Attempt {attempt}/{MAX_RETRIES}")
            time.sleep(BACKOFF_BASE ** attempt)

    log.error(f"   💀  Email FAILED after {MAX_RETRIES} attempts for {recipient_email}")
    return False


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 9 — REPORT GENERATOR
# ════════════════════════════════════════════════════════════════════════════════

def save_report(results: list[dict]) -> None:
    """
    Save a post-run CSV report: one row per lead with status of each stage.
    """
    if not results:
        return
    df = pd.DataFrame(results)
    df.to_csv(REPORT_FILE, index=False)
    log.info(f"📊  Pipeline report saved → {REPORT_FILE.name}")


def print_summary(results: list[dict], start_time: float) -> None:
    """Print a rich terminal summary after the pipeline completes."""
    total      = len(results)
    enriched   = sum(1 for r in results if r.get("claude_status") == "success")
    crm_ok     = sum(1 for r in results if r.get("hubspot_status") in ("created", "updated"))
    emails_ok  = sum(1 for r in results if r.get("email_status") == "sent")
    failed     = total - max(enriched, crm_ok, emails_ok)
    elapsed    = time.time() - start_time

    print("\n")
    print("═" * 62)
    print("  NEXUS PIPELINE  ·  RUN COMPLETE")
    print("═" * 62)
    print(f"  ⏱  Elapsed Time       : {elapsed:.1f}s")
    print(f"  👥  Total Leads        : {total}")
    print(f"  🤖  Claude Enriched    : {enriched}/{total}")
    print(f"  🏢  HubSpot Synced     : {crm_ok}/{total}")
    print(f"  📧  Emails Dispatched  : {emails_ok}/{total}")
    print(f"  ⚠️   Partial/Failed     : {total - enriched + total - crm_ok + total - emails_ok}")
    print(f"  📋  Report             : data/pipeline_report.csv")
    print(f"  📝  Full Log           : logs/pipeline.log")
    print("═" * 62 + "\n")


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 10 — MAIN ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    start_time = time.time()

    print("\n" + "═" * 62)
    print("  ⚡  NEXUS SALES PIPELINE  ·  STARTING")
    print(f"  📅  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 62 + "\n")

    # ── 1. Load & validate credentials ──
    creds = load_and_validate_env()

    # ── 2. Load leads ──
    leads = load_leads(LEADS_FILE)
    if not leads:
        sys.exit("❌  No valid leads found in leads.csv. Add leads and retry.")

    # ── 3. Initialise API clients ──
    log.info("🔗  Initialising API clients...")
    claude_client = anthropic.Anthropic(api_key=creds["ANTHROPIC_API_KEY"])
    hs_client     = HubSpot(access_token=creds["HUBSPOT_ACCESS_TOKEN"])
    log.info("✅  Clients ready (Anthropic + HubSpot)")

    results = []

    # ── 4. Process each lead ──
    for idx, lead in enumerate(leads, start=1):
        email = str(lead.get("Email", "")).strip()
        first_name = str(lead.get("First Name", "Friend")).strip()

        print(f"\n{'─' * 62}")
        log.info(f"[{idx}/{len(leads)}]  Processing: {first_name} — {email}")

        result_row = {
            "First Name":      first_name,
            "Last Name":       lead.get("Last Name", ""),
            "Email":           email,
            "Company":         lead.get("Company", ""),
            "Job Title":       lead.get("Job Title", ""),
            "claude_status":   "skipped",
            "claude_pitch":    "",
            "hubspot_status":  "skipped",
            "hubspot_id":      "",
            "email_status":    "skipped",
            "timestamp":       datetime.now().isoformat(),
        }

        # ── Validate email format ──
        if not is_valid_email(email):
            log.warning(f"   ✗  Invalid email format: '{email}' — skipping lead")
            result_row["email_status"] = "invalid_email"
            results.append(result_row)
            continue

        # ── Stage A: Claude Enrichment ──
        log.info(f"   Stage 1 · Claude Enrichment...")
        pitch = call_claude_with_retry(claude_client, lead)
        if pitch:
            result_row["claude_status"] = "success"
            result_row["claude_pitch"]  = pitch
        else:
            result_row["claude_status"] = "failed"
            pitch = f"Noticed the work your team is doing at {lead.get('Company')} — thought it was worth reaching out."
            log.warning(f"   ↳  Using fallback pitch for {email}")

        # ── Rate limit courtesy pause ──
        time.sleep(RATE_LIMIT_WAIT)

        # ── Stage B: HubSpot CRM Upsert ──
        log.info(f"   Stage 2 · HubSpot CRM Sync...")
        contact_id, action = upsert_hubspot_contact(hs_client, lead, pitch)
        result_row["hubspot_status"] = action
        result_row["hubspot_id"]     = contact_id or ""

        # ── Stage C: Email Dispatch ──
        log.info(f"   Stage 3 · Email Dispatch...")
        sent = send_email(
            sender_email=creds["SENDER_EMAIL"],
            app_password=creds["EMAIL_APP_PASSWORD"],
            recipient_email=email,
            first_name=first_name,
            pitch=pitch,
        )
        result_row["email_status"] = "sent" if sent else "failed"

        results.append(result_row)

    # ── 5. Save report & print summary ──
    save_report(results)
    print_summary(results, start_time)


# ════════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
