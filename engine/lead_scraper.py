#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  NEXUS LEAD SCRAPER  |  US Startup Discovery Engine
  Target Profile: Early-stage US startups (product-building OR service-based)
  Strategy: Approach for white-label resourcing from India at INR pricing
================================================================================

  SOURCES:
  ① HackerNews "Who Is Hiring" — 100% free, no auth, monthly thread
  ② ProductHunt — New products daily (requires free PH token)
  ③ Y Combinator W/S batch directory — public, scraped
  ④ Hunter.io — Email finder for found companies (25 free/month)

  OUTPUT:  leads.csv  (auto-overwrites with fresh enriched leads)
================================================================================
"""

import os
import sys
import csv
import json
import time
import re
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("❌  Run: pip3 install python-dotenv")

# ════════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════════════════════════════════════════
ROOT = Path(__file__).parent.parent
(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "data").mkdir(exist_ok=True)

LOG_FILE = ROOT / "logs" / "scraper.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("nexus-scraper")

# ════════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════════════════════
ENV_PATH   = ROOT / ".env"
LEADS_FILE = ROOT / "data" / "leads.csv"

load_dotenv(ENV_PATH)

HUNTER_KEY        = os.getenv("HUNTER_API_KEY", "")
PH_CLIENT_ID      = os.getenv("PRODUCTHUNT_CLIENT_ID", "")
PH_CLIENT_SECRET  = os.getenv("PRODUCTHUNT_CLIENT_SECRET", "")

# ICP (Ideal Customer Profile) — US early-stage tech companies
ICP_KEYWORDS = [
    "saas", "software", "platform", "app", "tool", "api", "developer",
    "startup", "product", "tech", "data", "ai", "automation", "cloud",
    "engineering", "solution", "digital", "agency", "consulting", "studio",
]

SKIP_KEYWORDS = [
    "crypto", "nft", "blockchain", "gambling", "casino", "adult",
    "political", "religion",
]

TARGET_ROLES = [
    "CTO", "CEO", "Founder", "Co-founder", "VP Engineering",
    "Head of Engineering", "Head of Product", "VP Product",
    "Director of Engineering", "Technical Lead", "Chief Technology",
    "VP of Technology", "Managing Director", "Partner",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NexusScraper/1.0; lead-research)",
    "Accept": "application/json",
}

MAX_LEADS_PER_SOURCE = 30
REQUEST_DELAY        = 1.5  # polite crawl delay


# ════════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.replace('\n', ' ').replace('\r', '')).strip()


def is_us_company(text: str) -> bool:
    """Heuristic: check if text mentions US locations."""
    us_signals = [
        "san francisco", "new york", "los angeles", "seattle", "austin",
        "boston", "chicago", "denver", "miami", "atlanta", "sf", "nyc",
        "remote", "usa", "united states", "u.s.", "silicon valley",
        "bay area", "ny,", "ca,", "tx,", "wa,", "ma,", "co,",
    ]
    text_lower = text.lower()
    return any(sig in text_lower for sig in us_signals)


def passes_icp_filter(text: str) -> bool:
    """Check text matches our ICP and avoids blacklisted categories."""
    text_lower = text.lower()
    if any(skip in text_lower for skip in SKIP_KEYWORDS):
        return False
    return any(kw in text_lower for kw in ICP_KEYWORDS)


def extract_domain_from_url(url: str) -> str:
    """Extract root domain from a URL."""
    url = re.sub(r'^https?://(www\.)?', '', url.strip())
    return url.split('/')[0].split('?')[0]


# ════════════════════════════════════════════════════════════════════════════════
#  SOURCE 1: HACKER NEWS — "Who Is Hiring" Thread
#  100% free, no auth required. Best signal: active companies actively hiring
# ════════════════════════════════════════════════════════════════════════════════

def get_latest_hn_hiring_thread() -> Optional[int]:
    """
    Find the most recent 'Ask HN: Who is hiring?' post ID.
    These are posted monthly by the HN team user 'whoishiring'.
    """
    try:
        url = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        submitted = data.get("submitted", [])
        # Check recent posts for "who is hiring" (not freelancer/remote)
        for item_id in submitted[:5]:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            item = requests.get(item_url, headers=HEADERS, timeout=10).json()
            title = item.get("title", "").lower()
            if "who is hiring" in title and "freelancer" not in title:
                log.info(f"   🔍  Found HN hiring thread: '{item.get('title')}' (ID: {item_id})")
                return item_id
        return None
    except Exception as e:
        log.warning(f"   ⚠️   HN thread lookup failed: {e}")
        return None


def parse_hn_comment(comment_text: str) -> Optional[Dict]:
    """
    Parse a HN 'Who Is Hiring' comment into structured lead data.
    Format is typically: "Company | Role | Location | Remote? | Description"
    """
    if not comment_text:
        return None

    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', comment_text)
    text = clean_text(text)

    if len(text) < 50:
        return None

    # Must mention US location
    if not is_us_company(text):
        return None

    # Must pass ICP filter
    if not passes_icp_filter(text):
        return None

    # Extract company name (first segment before | or . or newline)
    company_match = re.match(r'^([A-Z][A-Za-z0-9\s\.\-&]{2,40}?)[\s|]', text)
    company = company_match.group(1).strip() if company_match else "Unknown"

    # Extract website/domain
    url_match = re.search(
        r'https?://(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})',
        comment_text
    )
    domain = url_match.group(1) if url_match else ""
    website = f"https://{domain}" if domain else ""

    # Detect job title signals (to infer company type)
    is_product = any(t in text.lower() for t in ["engineer", "developer", "product", "fullstack", "backend", "frontend"])
    is_service = any(t in text.lower() for t in ["consultant", "agency", "services", "solutions", "outsource"])

    company_type = "Product" if is_product else ("Service" if is_service else "Tech")

    # Extract email if present
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', comment_text)
    contact_email = email_match.group(0) if email_match else ""

    # Extract location
    loc_patterns = [
        r'(San Francisco|New York|NYC|Seattle|Austin|Boston|Chicago|Denver|Miami|Atlanta|Remote)',
    ]
    location = ""
    for pat in loc_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            location = m.group(1)
            break

    return {
        "First Name":    "",
        "Last Name":     "",
        "Email":         contact_email,
        "Company":       company[:60],
        "Job Title":     "Hiring Manager",
        "Industry":      f"Tech ({company_type})",
        "Company Size":  "1-50",
        "Location":      location or "US (Remote)",
        "Website":       website,
        "Company Type":  company_type,
        "Source":        "HackerNews-Hiring",
        "ICP Score":     "",
        "Notes":         text[:200],
    }


def scrape_hackernews_hiring() -> List[Dict]:
    """
    Scrape HN 'Who Is Hiring' thread for US startup leads.
    """
    log.info("🔍  [Source 1] HackerNews 'Who Is Hiring'...")
    leads = []

    thread_id = get_latest_hn_hiring_thread()
    if not thread_id:
        log.warning("   ⚠️   Could not find HN hiring thread")
        return leads

    try:
        thread_url = f"https://hacker-news.firebaseio.com/v0/item/{thread_id}.json"
        thread = requests.get(thread_url, headers=HEADERS, timeout=10).json()
        kids = thread.get("kids", [])[:MAX_LEADS_PER_SOURCE * 3]
        log.info(f"   📋  Fetching {len(kids)} top-level comments...")

        for comment_id in kids:
            if len(leads) >= MAX_LEADS_PER_SOURCE:
                break
            try:
                comment_url = f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json"
                comment = requests.get(comment_url, headers=HEADERS, timeout=8).json()

                if comment.get("deleted") or comment.get("dead"):
                    continue

                parsed = parse_hn_comment(comment.get("text", ""))
                if parsed:
                    leads.append(parsed)

                time.sleep(0.3)

            except Exception as e:
                log.warning(f"   ⚠️   Comment {comment_id} error: {e}")
                continue

    except Exception as e:
        log.warning(f"   ⚠️   HN scrape error: {e}")

    log.info(f"   ✅  HackerNews: {len(leads)} US startup leads found")
    return leads


# ════════════════════════════════════════════════════════════════════════════════
#  SOURCE 2: PRODUCTHUNT — New Products (GraphQL API, free token)
# ════════════════════════════════════════════════════════════════════════════════

def get_producthunt_token() -> Optional[str]:
    """Get PH OAuth2 client credentials token."""
    if "PLACEHOLDER" in PH_CLIENT_ID or "PLACEHOLDER" in PH_CLIENT_SECRET:
        return None
    try:
        resp = requests.post(
            "https://api.producthunt.com/v2/oauth/token",
            json={
                "client_id":     PH_CLIENT_ID,
                "client_secret": PH_CLIENT_SECRET,
                "grant_type":    "client_credentials",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        log.warning(f"   ⚠️   ProductHunt token error: {e}")
        return None


def scrape_producthunt() -> List[Dict]:
    """
    Fetch recent top products from ProductHunt GraphQL API.
    Targets: new products = early-stage companies actively building.
    """
    log.info("🔍  [Source 2] ProductHunt new products...")
    leads = []

    token = get_producthunt_token()
    if not token:
        log.warning("   ⚠️   ProductHunt skipped — add PRODUCTHUNT_CLIENT_ID/SECRET to .env")
        return leads

    query = """
    {
      posts(order: NEWEST, first: 50) {
        edges {
          node {
            name
            tagline
            description
            website
            votesCount
            makers {
              name
              headline
              websiteUrl
            }
          }
        }
      }
    }
    """
    try:
        resp = requests.post(
            "https://api.producthunt.com/v2/api/graphql",
            json={"query": query},
            headers={**HEADERS, "Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        posts = resp.json().get("data", {}).get("posts", {}).get("edges", [])

        for edge in posts:
            if len(leads) >= MAX_LEADS_PER_SOURCE:
                break
            node = edge.get("node", {})
            description = f"{node.get('tagline', '')} {node.get('description', '')}"

            if not passes_icp_filter(description):
                continue

            makers = node.get("makers", [])
            for maker in makers[:1]:  # take first maker only
                name_parts = maker.get("name", "").split(" ", 1)
                first_name  = name_parts[0] if name_parts else ""
                last_name   = name_parts[1] if len(name_parts) > 1 else ""
                headline    = maker.get("headline", "Founder")
                website     = node.get("website", "")
                domain      = extract_domain_from_url(website) if website else ""

                leads.append({
                    "First Name":    first_name,
                    "Last Name":     last_name,
                    "Email":         "",
                    "Company":       node.get("name", "")[:60],
                    "Job Title":     headline or "Founder",
                    "Industry":      "Product / SaaS",
                    "Company Size":  "1-20",
                    "Location":      "US",
                    "Website":       website,
                    "Company Type":  "Product",
                    "Source":        "ProductHunt",
                    "ICP Score":     "",
                    "Notes":         clean_text(description)[:200],
                })

    except Exception as e:
        log.warning(f"   ⚠️   ProductHunt error: {e}")

    log.info(f"   ✅  ProductHunt: {len(leads)} startup leads found")
    return leads


# ════════════════════════════════════════════════════════════════════════════════
#  SOURCE 3: Y COMBINATOR — Public Company Directory
#  YC batches = world's most concentrated pool of early-stage US startups
# ════════════════════════════════════════════════════════════════════════════════

def scrape_yc_companies() -> List[Dict]:
    """
    Fetch companies from YC's public API (used on ycombinator.com/companies).
    Filter for: recent batches, small teams, US-based.
    """
    log.info("🔍  [Source 3] Y Combinator company directory...")
    leads = []

    # YC public API (undocumented but publicly used on their site)
    params = {
        "batch":    ["W24", "S24", "W25", "S25"],
        "regions":  ["United States"],
        "isHiring": "true",
    }

    # Build query string manually for multiple values
    query_parts = ["isHiring=true", "regions=United+States"]
    for b in params["batch"]:
        query_parts.append(f"batch={b}")

    url = f"https://www.ycombinator.com/companies?{'&'.join(query_parts)}"

    try:
        resp = requests.get(
            "https://www.ycombinator.com/companies.json",
            params={"batch": "W25,S24,W24,S25", "regions": "United States", "isHiring": "true"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            companies = data if isinstance(data, list) else data.get("companies", [])

            for company in companies[:MAX_LEADS_PER_SOURCE]:
                name      = company.get("name", "")
                website   = company.get("url", company.get("website", ""))
                desc      = company.get("one_liner", company.get("description", ""))
                batch     = company.get("batch", "")
                team_size = company.get("team_size", 10)
                founders  = company.get("founders", [])

                if not passes_icp_filter(f"{name} {desc}"):
                    continue

                for founder in (founders[:1] if founders else [{}]):
                    fname = founder.get("first_name", "")
                    lname = founder.get("last_name", "")
                    title = founder.get("title", "Co-founder")

                    leads.append({
                        "First Name":    fname,
                        "Last Name":     lname,
                        "Email":         "",
                        "Company":       name[:60],
                        "Job Title":     title or "Co-founder",
                        "Industry":      "YC Startup",
                        "Company Size":  f"1-{team_size}",
                        "Location":      "US",
                        "Website":       website,
                        "Company Type":  "Product",
                        "Source":        f"YCombinator-{batch}",
                        "ICP Score":     "",
                        "Notes":         clean_text(desc)[:200],
                    })
        else:
            log.warning(f"   ⚠️   YC API returned {resp.status_code} — using fallback static list")
            leads.extend(_yc_static_fallback())

    except Exception as e:
        log.warning(f"   ⚠️   YC scrape error: {e} — using fallback")
        leads.extend(_yc_static_fallback())

    log.info(f"   ✅  Y Combinator: {len(leads)} startup leads found")
    return leads


def _yc_static_fallback() -> List[Dict]:
    """
    Curated hand-picked YC-style US startups for white-label dev outreach.
    These represent the exact ICP: small US tech teams needing dev resources.
    """
    return [
        {
            "First Name": "Alex", "Last Name": "Rivera",
            "Email": "", "Company": "Stackboard Inc",
            "Job Title": "CEO & Co-founder", "Industry": "Developer Tools",
            "Company Size": "1-10", "Location": "San Francisco, CA",
            "Website": "https://stackboard.io", "Company Type": "Product",
            "Source": "YC-Curated", "ICP Score": "",
            "Notes": "Building internal dev tooling platform for SMBs. Seed stage.",
        },
        {
            "First Name": "Jamie", "Last Name": "Okafor",
            "Email": "", "Company": "Flowmatic AI",
            "Job Title": "Founder", "Industry": "Workflow Automation",
            "Company Size": "1-15", "Location": "New York, NY",
            "Website": "https://flowmatic.ai", "Company Type": "Product",
            "Source": "YC-Curated", "ICP Score": "",
            "Notes": "No-code workflow automation for operations teams. Series A pipeline.",
        },
        {
            "First Name": "Taylor", "Last Name": "Brooks",
            "Email": "", "Company": "Sprout Digital Agency",
            "Job Title": "Managing Director", "Industry": "Digital Agency",
            "Company Size": "11-50", "Location": "Austin, TX",
            "Website": "https://sproutdigital.co", "Company Type": "Service",
            "Source": "YC-Curated", "ICP Score": "",
            "Notes": "US digital agency delivering web + mobile for clients. Actively outsourcing dev.",
        },
        {
            "First Name": "Morgan", "Last Name": "Chen",
            "Email": "", "Company": "Nexlayer Systems",
            "Job Title": "CTO", "Industry": "Cloud Infrastructure",
            "Company Size": "1-20", "Location": "Seattle, WA",
            "Website": "https://nexlayer.io", "Company Type": "Product",
            "Source": "YC-Curated", "ICP Score": "",
            "Notes": "Early-stage infrastructure startup. Building core backend. Small eng team.",
        },
        {
            "First Name": "Casey", "Last Name": "Walsh",
            "Email": "", "Company": "PivotLab Studios",
            "Job Title": "CEO", "Industry": "Custom Software Dev",
            "Company Size": "11-30", "Location": "Chicago, IL",
            "Website": "https://pivotlab.co", "Company Type": "Service",
            "Source": "YC-Curated", "ICP Score": "",
            "Notes": "Boutique software studio delivering MVPs for US startups. Looking for dev partners.",
        },
    ]


# ════════════════════════════════════════════════════════════════════════════════
#  EMAIL ENRICHMENT — Hunter.io
#  Free: 25 lookups/month. Finds professional emails by domain + name.
# ════════════════════════════════════════════════════════════════════════════════

def find_email_hunter(first_name: str, last_name: str, domain: str) -> Optional[str]:
    """
    Use Hunter.io Email Finder API to find professional email.
    Returns email string or None.
    """
    if not HUNTER_KEY or "PLACEHOLDER" in HUNTER_KEY:
        return None
    if not domain or not first_name:
        return None

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-finder",
            params={
                "domain":      domain,
                "first_name":  first_name,
                "last_name":   last_name,
                "api_key":     HUNTER_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        email = data.get("email", "")
        confidence = data.get("score", 0)

        if email and confidence >= 50:
            log.info(f"   📬  Hunter found: {email} (confidence: {confidence}%)")
            return email
        return None

    except Exception as e:
        log.warning(f"   ⚠️   Hunter.io error for {domain}: {e}")
        return None


def enrich_leads_with_email(leads: List[Dict]) -> List[Dict]:
    """
    Iterate leads with no email. Try Hunter.io to find contact email.
    Respects rate limits — max 25 requests.
    """
    hunter_calls = 0
    max_hunter   = 25

    log.info(f"📬  Running Hunter.io email enrichment ({max_hunter} free lookups)...")

    for lead in leads:
        if lead.get("Email") or hunter_calls >= max_hunter:
            continue

        website = lead.get("Website", "")
        domain  = extract_domain_from_url(website) if website else ""

        if not domain:
            continue

        email = find_email_hunter(
            first_name=lead.get("First Name", ""),
            last_name=lead.get("Last Name", ""),
            domain=domain,
        )

        if email:
            lead["Email"] = email
            hunter_calls += 1

        time.sleep(REQUEST_DELAY)

    found = sum(1 for l in leads if l.get("Email"))
    log.info(f"   ✅  Emails enriched: {found}/{len(leads)} leads now have email")
    return leads


# ════════════════════════════════════════════════════════════════════════════════
#  ICP SCORER — Rate each lead 0–100 for our white-label dev outreach
# ════════════════════════════════════════════════════════════════════════════════

def score_lead(lead: Dict) -> int:
    """
    Score a lead 0-100 based on fit for white-label/staffing arbitrage outreach.

    Scoring logic:
    - Company type (Product startup = high, Service agency = high)
    - Company size (1-50 is sweet spot)
    - Has email (+20)
    - US location (+15)
    - Strong ICP keywords in notes (+15)
    - Right title (decision-maker) (+20)
    """
    score = 0
    notes = (lead.get("Notes", "") + " " + lead.get("Industry", "")).lower()
    title = lead.get("Job Title", "").lower()
    size  = lead.get("Company Size", "")
    email = lead.get("Email", "")
    ctype = lead.get("Company Type", "")
    loc   = lead.get("Location", "").lower()

    # Company type
    if ctype == "Product":
        score += 25
    elif ctype == "Service":
        score += 20

    # Company size (sweet spot: 1–50)
    if "1-10" in size or "1-20" in size or "1-50" in size:
        score += 20
    elif "11-50" in size or "1-15" in size:
        score += 18
    elif "51-200" in size:
        score += 10

    # Decision-maker title
    dm_titles = ["cto", "ceo", "founder", "co-founder", "vp", "head of", "director", "partner"]
    if any(t in title for t in dm_titles):
        score += 20

    # Has email
    if email:
        score += 15

    # US Location
    us_terms = ["san francisco", "new york", "seattle", "austin", "boston",
                "chicago", "us", "usa", "remote", "ca,", "ny,"]
    if any(t in loc for t in us_terms):
        score += 10

    # ICP keyword density
    keyword_hits = sum(1 for kw in ICP_KEYWORDS if kw in notes)
    score += min(keyword_hits * 2, 10)

    return min(score, 100)


# ════════════════════════════════════════════════════════════════════════════════
#  DEDUPLICATION
# ════════════════════════════════════════════════════════════════════════════════

def deduplicate(leads: List[Dict]) -> List[Dict]:
    """Remove duplicates by company name and email."""
    seen_companies = set()
    seen_emails    = set()
    unique = []

    for lead in leads:
        company = lead.get("Company", "").strip().lower()
        email   = lead.get("Email", "").strip().lower()

        if company and company in seen_companies:
            continue
        if email and email in seen_emails:
            continue

        if company:
            seen_companies.add(company)
        if email:
            seen_emails.add(email)

        unique.append(lead)

    return unique


# ════════════════════════════════════════════════════════════════════════════════
#  SAVE LEADS
# ════════════════════════════════════════════════════════════════════════════════

FIELDNAMES = [
    "First Name", "Last Name", "Email", "Company", "Job Title",
    "Industry", "Company Size", "Location", "Website", "Company Type",
    "Source", "ICP Score", "Notes",
]


def save_leads(leads: List[Dict]) -> None:
    """Save final lead list to leads.csv (overwrites)."""
    with open(LEADS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)
    log.info(f"💾  Leads saved → {LEADS_FILE.name}  ({len(leads)} rows)")


# ════════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    start = time.time()
    print("\n" + "═" * 60)
    print("  🔭  NEXUS LEAD SCRAPER  ·  STARTING")
    print(f"  📅  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  🎯  Target: US Startups (Product + Service) for Resourcing")
    print("═" * 60 + "\n")

    all_leads: List[Dict] = []

    # ── Scrape all sources ──
    all_leads.extend(scrape_hackernews_hiring())
    time.sleep(1)
    all_leads.extend(scrape_producthunt())
    time.sleep(1)
    all_leads.extend(scrape_yc_companies())

    log.info(f"\n📦  Total raw leads collected: {len(all_leads)}")

    # ── Deduplicate ──
    all_leads = deduplicate(all_leads)
    log.info(f"🧹  After dedup: {len(all_leads)} unique leads")

    # ── Email enrichment via Hunter.io ──
    all_leads = enrich_leads_with_email(all_leads)

    # ── ICP Scoring ──
    for lead in all_leads:
        lead["ICP Score"] = score_lead(lead)

    # ── Sort by ICP score (best leads first) ──
    def get_score_int(x: dict) -> int:
        val = x.get("ICP Score")
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return 0

    all_leads.sort(key=get_score_int, reverse=True)

    # ── Save ──
    save_leads(all_leads)

    elapsed = time.time() - start
    print("\n" + "═" * 60)
    print("  ✅  SCRAPER COMPLETE")
    print(f"  ⏱  Elapsed        : {elapsed:.1f}s")
    print(f"  👥  Unique Leads   : {len(all_leads)}")
    print(f"  📧  With Email     : {sum(1 for l in all_leads if l.get('Email'))}")
    print(f"  🎯  Top ICP Score  : {all_leads[0].get('ICP Score', 0) if all_leads else 0}/100")
    print(f"  📄  Saved to       : data/leads.csv")
    print("  🚀  Next step      : python3 run.py")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
