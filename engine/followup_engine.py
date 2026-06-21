#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  NEXUS FOLLOW-UP ENGINE  |  Automated B2B Outreach Drip Sequence
  Built for: India-based Software Dev & AI Data Solutions
  Author:    followup_engine.py v1.0
================================================================================

  DRIP SEQUENCE SCHEDULE:
  - Day 0: Initial Outreach Email (sent by pipeline.py)
  - Day 3: Casual Bump (float to top of inbox)
  - Day 7: Value Add (send case study brief / offer resources)
  - Day 10: Social Proof & Resourcing Math (why offshore white-label works)
  - Day 14: Breakup Email (last touch, polite close)
================================================================================
"""

import os
import sys
import csv
import time
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

# Ensure we can import from pipeline.py
try:
    from pipeline import load_and_validate_env, detect_smtp_provider, is_valid_email
except ImportError:
    sys.exit("❌  Could not import from pipeline.py. Make sure pipeline.py is in the same directory.")

# ════════════════════════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ════════════════════════════════════════════════════════════════════════════════
ROOT = Path(__file__).parent.parent
(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "data").mkdir(exist_ok=True)

LOG_FILE = ROOT / "logs" / "followup.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("nexus-followup")

# ════════════════════════════════════════════════════════════════════════════════
#  CONFIG & FILES
# ════════════════════════════════════════════════════════════════════════════════
TRACKER_FILE = ROOT / "data" / "followup_tracker.csv"
REPORT_FILE  = ROOT / "data" / "pipeline_report.csv"

# Sender settings
SENDER_NAME     = os.getenv("SENDER_NAME", "Founder")
COMPANY_NAME    = os.getenv("COMPANY_NAME", "YourCompany.ai")
COMPANY_TAGLINE = os.getenv("COMPANY_TAGLINE", "Custom AI Systems & Data Engineering")
CALENDLY_LINK   = os.getenv("CALENDLY_LINK", "https://calendly.com/yourcompany/15min")

# Follow-up delays
DELAYS = {
    1: 3,   # Day 3: Casual Bump
    2: 7,   # Day 7: Value Add
    3: 10,  # Day 10: Social Proof
    4: 14   # Day 14: Breakup
}

# ════════════════════════════════════════════════════════════════════════════════
#  EMAIL TEMPLATES (CEO VOICE)
# ════════════════════════════════════════════════════════════════════════════════

def get_followup_subject(first_name: str) -> str:
    return f"Re: Quick thought on {first_name}'s roadmap"


def build_followup_html(first_name: str, company: str, stage: int) -> str:
    """Build premium HTML body for follow-up emails."""
    
    if stage == 1:
        content_html = f"""
        <p class="body-text">
          Just wanted to float this back to the top of your inbox in case you've been swamped.
        </p>
        <p class="body-text">
          Would love to see if you have any engineering capacity gaps we can help {company} cover this month.
        </p>
        """
    elif stage == 2:
        content_html = f"""
        <p class="body-text">
          Thought you might find this interesting. We recently helped a US startup migrate their legacy web-scraping infra to a serverless queue system. It cut their API costs by 55% while doubling their data throughput.
        </p>
        <p class="body-text">
          I wrote up a short 1-page summary showing the architecture and code structure. Let me know if you'd like me to send it over.
        </p>
        """
    elif stage == 3:
        content_html = f"""
        <p class="body-text">
          Checking in once more. A lot of US startups and digital agencies we partner with use us as their white-label engineering team.
        </p>
        <p class="body-text">
          They handle client-facing product management, and we do the actual building in Python and React. They get to charge US agency rates, while paying India dev rates.
        </p>
        <p class="body-text">
          If you have any upcoming MVPs or backlog features you want to get shipped quickly, we can spin up a dedicated dev for you in 48 hours.
        </p>
        """
    elif stage == 4:
        content_html = f"""
        <p class="body-text">
          I assume you're either fully sorted for engineering or the timing isn't right. I won't email you again.
        </p>
        <p class="body-text">
          If you ever want to chat about dev or AI resourcing in the future, you can always grab a slot here: <a href="{CALENDLY_LINK}" style="color:#7c3aed;">{CALENDLY_LINK}</a>.
        </p>
        <p class="body-text">
          Otherwise, wish you and {company} all the best.
        </p>
        """
    else:
        content_html = ""

    # Wrapper layout
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
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
    .body {{
      padding: 40px;
    }}
    .greeting {{
      font-size: 16px;
      font-weight: 500;
      color: #1a1a2e;
      margin-bottom: 20px;
    }}
    .body-text {{
      font-size: 15px;
      line-height: 1.7;
      color: #374151;
      margin-bottom: 18px;
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
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="body">
      <div class="greeting">Hey {first_name},</div>
      {content_html}
      <hr class="divider" />
      <div class="signature">
        <strong>{SENDER_NAME}</strong><br/>
        {COMPANY_NAME} — {COMPANY_TAGLINE}<br/>
        <a href="{CALENDLY_LINK}" style="color:#7c3aed;">{CALENDLY_LINK}</a>
      </div>
    </div>
  </div>
</body>
</html>"""


def build_followup_plain(first_name: str, company: str, stage: int) -> str:
    """Plain-text fallback for follow-up emails."""
    if stage == 1:
        body = "Just wanted to float this back to the top of your inbox in case you've been swamped.\n\nWould love to see if you have any engineering capacity gaps we can help cover this month."
    elif stage == 2:
        body = "Thought you might find this interesting. We recently helped a US startup migrate their legacy web-scraping infra to a serverless queue system. It cut their API costs by 55% while doubling their data throughput.\n\nI wrote up a short 1-page summary showing the architecture and code structure. Let me know if you'd like me to send it over."
    elif stage == 3:
        body = "Checking in once more. A lot of US startups and digital agencies we partner with use us as their white-label engineering team.\n\nThey handle client-facing product management, and we do the actual building. They charge US agency rates while paying India rates.\n\nIf you have any upcoming MVPs or backlog features you want to get shipped quickly, we can spin up a dedicated dev for you in 48 hours."
    elif stage == 4:
        body = f"I assume you're either fully sorted for engineering or the timing isn't right. I won't email you again.\n\nIf you ever want to chat about dev or AI resourcing in the future, you can always grab a slot here: {CALENDLY_LINK}\n\nOtherwise, wish you and {company} all the best."
    else:
        body = ""

    return f"Hey {first_name},\n\n{body}\n\n—\n{SENDER_NAME}\n{COMPANY_NAME} — {COMPANY_TAGLINE}\n{CALENDLY_LINK}"

# ════════════════════════════════════════════════════════════════════════════════
#  SMTP DISPATCHER
# ════════════════════════════════════════════════════════════════════════════════

def send_followup_email(
    sender_email: str,
    app_password: str,
    recipient_email: str,
    first_name: str,
    company: str,
    stage: int,
) -> bool:
    """Send a specific follow-up stage email via SMTP."""
    subject = get_followup_subject(first_name)
    smtp_config = detect_smtp_provider(sender_email)

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{sender_email}>"
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg["Reply-To"] = sender_email

    # Add custom header to aid threading if client supports it
    msg["Subject"] = subject

    plain_body = build_followup_plain(first_name, company, stage)
    html_body = build_followup_html(first_name, company, stage)

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            log.info(f"   📧  Follow-up #{stage} SENT → {recipient_email}")
            return True
    except Exception as e:
        log.error(f"   ❌  SMTP failed to send follow-up #{stage} to {recipient_email}: {e}")
        return False

# ════════════════════════════════════════════════════════════════════════════════
#  TRACKER DATA MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════════

def parse_iso_date(dt_str: str) -> datetime:
    """Parse only the date part of an ISO string to make parsing bulletproof in python 3.9."""
    try:
        date_part = dt_str.split("T")[0]
        return datetime.strptime(date_part, "%Y-%m-%d")
    except Exception:
        return datetime.now()


def initialize_tracker_from_report() -> List[Dict[str, Any]]:
    """Create a new tracker list using sent leads from pipeline_report.csv."""
    if not REPORT_FILE.exists():
        log.warning("⚠️   No pipeline_report.csv found. Run pipeline.py first.")
        return []

    log.info(f"📋  Initializing followup_tracker.csv from {REPORT_FILE.name}...")
    leads = []
    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("email_status") == "sent":
                timestamp_val = row.get("timestamp") or datetime.now().isoformat()
                leads.append({
                    "Email": row.get("Email", ""),
                    "First Name": row.get("First Name", "Friend"),
                    "Company": row.get("Company", ""),
                    "Job Title": row.get("Job Title", "Hiring Manager"),
                    "Initial Sent Date": timestamp_val,
                    "Last Followup Number": "0",
                    "Last Followup Date": timestamp_val,
                    "Status": "Active"
                })

    if leads:
        save_tracker(leads)
        log.info(f"✅  Initialized followup_tracker.csv with {len(leads)} active leads.")
    else:
        log.warning("⚠️   No sent leads found in pipeline_report.csv to import.")
    
    return leads


def load_tracker() -> List[Dict[str, Any]]:
    """Load the follow-up tracker file, or initialize it if missing."""
    if not TRACKER_FILE.exists():
        return initialize_tracker_from_report()

    leads = []
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append({
                "Email": row.get("Email", ""),
                "First Name": row.get("First Name", "Friend"),
                "Company": row.get("Company", ""),
                "Job Title": row.get("Job Title", ""),
                "Initial Sent Date": row.get("Initial Sent Date", datetime.now().isoformat()),
                "Last Followup Number": row.get("Last Followup Number", "0"),
                "Last Followup Date": row.get("Last Followup Date", datetime.now().isoformat()),
                "Status": row.get("Status", "Active")
            })
    return leads


def save_tracker(leads: List[Dict[str, Any]]) -> None:
    """Save the current tracking state back to followup_tracker.csv."""
    fieldnames = [
        "Email", "First Name", "Company", "Job Title", 
        "Initial Sent Date", "Last Followup Number", 
        "Last Followup Date", "Status"
    ]
    with open(TRACKER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)

# ════════════════════════════════════════════════════════════════════════════════
#  MAIN PROCESSOR
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("\n" + "═" * 60)
    print("  ⚡  NEXUS FOLLOW-UP ENGINE  ·  STARTING")
    print(f"  📅  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 60 + "\n")

    # 1. Load and validate SMTP credentials from env
    creds = load_and_validate_env()
    sender_email = creds["SENDER_EMAIL"]
    app_password = creds["EMAIL_APP_PASSWORD"]

    # 2. Load tracker
    leads = load_tracker()
    if not leads:
        print("❌  No leads currently tracked in followup_tracker.csv. Run pipeline.py first.")
        sys.exit(0)

    today = datetime.now()
    updated_count = 0

    log.info(f"🔍  Scanning {len(leads)} tracked leads for pending follow-ups...")

    for lead in leads:
        if lead["Status"] != "Active":
            continue

        email = lead["Email"]
        first_name = lead["First Name"]
        company = lead["Company"]
        initial_sent_date = parse_iso_date(lead["Initial Sent Date"])
        last_fn_num = int(lead["Last Followup Number"])

        # Compute days elapsed since initial outreach
        elapsed_days = (today - initial_sent_date).days

        # Determine if we should send the next follow-up stage
        next_stage = last_fn_num + 1
        if next_stage not in DELAYS:
            # Reached end of sequence
            lead["Status"] = "Finished"
            continue

        required_days = DELAYS[next_stage]

        log.info(f" Lead: {first_name} ({email}) | Days elapsed: {elapsed_days}/{required_days} for followup #{next_stage}")

        if elapsed_days >= required_days:
            log.info(f"   🚀  Triggering Follow-up #{next_stage} for {email}...")
            
            # Send the email
            success = send_followup_email(
                sender_email=sender_email,
                app_password=app_password,
                recipient_email=email,
                first_name=first_name,
                company=company,
                stage=next_stage
            )

            if success:
                lead["Last Followup Number"] = str(next_stage)
                lead["Last Followup Date"] = today.isoformat()
                
                # If they received the final breakup follow-up, mark as finished
                if next_stage == 4:
                    lead["Status"] = "Finished"
                    log.info(f"   🏁  Sequence finished for {email}")
                
                updated_count += 1
                time.sleep(3)  # pause between sends to be safe

    # Save changes
    if updated_count > 0:
        save_tracker(leads)
        log.info(f"💾  Saved updated tracking status. Dispatched {updated_count} follow-ups.")
    else:
        log.info("😴  No pending follow-ups found to send today.")

    print("\n" + "═" * 60)
    print("  🏁  FOLLOW-UP ENGINE RUN COMPLETE")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
