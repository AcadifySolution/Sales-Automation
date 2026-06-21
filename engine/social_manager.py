#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  NEXUS SOCIAL MANAGER  |  AI-Powered Business Page Automation
  Platforms: LinkedIn Company Page · Facebook Business Page · Clutch Profile
  Strategy: Thought leadership from an India-based dev + AI company targeting US
================================================================================

  WHAT THIS DOES:
  ① Generates 30-day content calendar using Claude 3.5 Sonnet
  ② Posts to LinkedIn Company Page via API
  ③ Posts to Facebook Business Page via Graph API
  ④ Generates Clutch profile copy + review request templates
  ⑤ Saves content calendar to content_calendar.csv for review

  POSTING CADENCE (CEO-recommended):
  - LinkedIn: 5x/week (Mon–Fri) — thought leadership + case studies
  - Facebook:  3x/week (Mon, Wed, Fri) — behind-the-scenes + results
  - Clutch:    Review requests sent after each project delivery
================================================================================
"""

import os
import sys
import csv
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

try:
    from dotenv import load_dotenv
    import anthropic
except ImportError:
    sys.exit("❌  Run: pip3 install python-dotenv anthropic")

# ════════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ════════════════════════════════════════════════════════════════════════════════
ROOT = Path(__file__).parent.parent
(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "content").mkdir(exist_ok=True)

LOG_FILE = ROOT / "logs" / "social.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("nexus-social")

# ════════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════════════════════════
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

ANTHROPIC_KEY         = os.getenv("ANTHROPIC_API_KEY", "")
LINKEDIN_TOKEN        = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_ORG_ID       = os.getenv("LINKEDIN_ORGANIZATION_ID", "")
FB_PAGE_TOKEN         = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
FB_PAGE_ID            = os.getenv("FACEBOOK_PAGE_ID", "")

COMPANY_NAME          = os.getenv("COMPANY_NAME", "YourCompany.ai")
SENDER_NAME           = os.getenv("SENDER_NAME", "Your Name")
FOUNDER_TITLE         = os.getenv("FOUNDER_TITLE", "Founder & CEO")
COMPANY_WEBSITE       = os.getenv("COMPANY_WEBSITE", "https://yourcompany.ai")
COMPANY_LINKEDIN      = os.getenv("COMPANY_LINKEDIN", "")
CALENDLY_LINK         = os.getenv("CALENDLY_LINK", "https://calendly.com/demo")

CALENDAR_FILE         = ROOT / "data" / "content_calendar.csv"
CLUTCH_TEMPLATES_FILE = ROOT / "content" / "clutch_templates.txt"

CLAUDE_MODEL          = "claude-3-5-sonnet-20241022"
POSTS_PER_PLATFORM    = 30  # 30 days of content

HEADERS = {"User-Agent": "NexusSocialManager/1.0"}


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — CONTENT GENERATION ENGINE (CLAUDE)
# ════════════════════════════════════════════════════════════════════════════════

# ── Content Pillars (CEO Strategy for Dev + AI company targeting US market) ──
CONTENT_PILLARS = [
    {
        "pillar": "Cost Arbitrage Education",
        "description": "Educate US startup founders on India resourcing math: $15/hr vs $150/hr, same quality.",
        "platforms": ["linkedin", "facebook"],
        "tone": "data-driven, confident, non-pushy",
        "cta": "Book a free team assessment call",
    },
    {
        "pillar": "Build-in-India Success Stories",
        "description": "Case studies of US companies scaling engineering with India teams. No names, metrics only.",
        "platforms": ["linkedin", "clutch"],
        "tone": "proof-based, specific metrics (e.g. shipped 3 features in 6 weeks at 40% of US cost)",
        "cta": "See how we work",
    },
    {
        "pillar": "Technical Thought Leadership",
        "description": "Deep insights on AI, data pipelines, system architecture, Python, React, cloud. Founder voice.",
        "platforms": ["linkedin"],
        "tone": "technical but accessible, opinionated, like a senior eng who also runs a company",
        "cta": "Follow for more technical insights",
    },
    {
        "pillar": "Behind the Build",
        "description": "Behind-the-scenes: team culture, sprint demos, office moments from India HQ.",
        "platforms": ["facebook", "linkedin"],
        "tone": "casual, authentic, humanising",
        "cta": "DM us if you're building something cool",
    },
    {
        "pillar": "The Resourcing Pitch (Direct)",
        "description": "Direct posts about our white-label model: US agency / startup brings us in, we deliver, they bill their clients.",
        "platforms": ["linkedin"],
        "tone": "direct, B2B, founder-to-founder",
        "cta": "Let's talk about your next sprint",
    },
    {
        "pillar": "Client Wins & Proof",
        "description": "Celebrating project deliveries, Clutch reviews, client testimonials. Social proof engine.",
        "platforms": ["linkedin", "facebook", "clutch"],
        "tone": "celebratory but humble, specific",
        "cta": "Read our Clutch reviews",
    },
]

PLATFORM_GUIDELINES = {
    "linkedin": {
        "max_chars": 3000,
        "style": "Professional but founder-authentic. Use short paragraphs (1-2 lines). Use line breaks liberally. Emojis: max 3. End with a CTA and 3-5 relevant hashtags.",
        "hashtags": ["#StartupGrowth", "#TechOutsourcing", "#IndiaToUS", "#SoftwareDevelopment", "#AIEngineering"],
    },
    "facebook": {
        "max_chars": 2000,
        "style": "More casual than LinkedIn. Conversational. Use a hook in the first line. Can use more emojis. Focus on stories and results. Single strong CTA.",
        "hashtags": ["#IndianTechCompany", "#StartupLife", "#SoftwareDev", "#AIStartup"],
    },
    "clutch": {
        "max_chars": 1500,
        "style": "Professional service description. Emphasise process, expertise, client outcomes. No fluff. Clutch audience is procurement/decision-makers.",
        "hashtags": [],
    },
}


def build_content_system_prompt() -> str:
    return f"""You are the content strategist and ghostwriter for {COMPANY_NAME}, 
an India-based software development and AI data engineering company led by {SENDER_NAME} ({FOUNDER_TITLE}).

Company facts:
- Based in India, serving US startups and agencies
- Core services: custom AI systems, data pipelines, full-stack development, automation
- Pricing model: India market rates (10–15x cheaper than US), US clients bill their own clients at US rates
- Team: senior Indian engineers (5–12 yrs experience), small & agile
- Mission: Be the invisible engineering backbone for ambitious US startups

Target audience: 
- US startup founders (seed to Series B) building products
- US digital agencies / service companies looking for dev partners
- CTOs and VPs Engineering with capacity gaps

Voice: Confident, direct, founder-authentic. Not corporate. Not salesy. Peer-to-peer.
Never say: "I hope this finds you well", "synergy", "leverage", "deep dive".
Always be: specific, opinionated, human."""


def generate_post(
    claude: anthropic.Anthropic,
    pillar: Dict,
    platform: str,
    post_number: int,
) -> str:
    """Generate a single platform-specific post using Claude."""
    guidelines = PLATFORM_GUIDELINES.get(platform, {})

    hashtags_val = guidelines.get('hashtags', [])
    hashtags_list = hashtags_val if isinstance(hashtags_val, list) else []

    prompt = f"""Generate social media post #{post_number} for {platform.upper()}.

Content Pillar: {pillar['pillar']}
Topic Direction: {pillar['description']}
Tone: {pillar['tone']}
Platform Style: {guidelines.get('style', '')}
Max Characters: {guidelines.get('max_chars', 2000)}
CTA to include: {pillar['cta']}
Suggested Hashtags: {' '.join(hashtags_list)}
Website: {COMPANY_WEBSITE}
Calendly: {CALENDLY_LINK}

IMPORTANT: 
- Make it feel like {SENDER_NAME} wrote it personally
- Do NOT start with "Are you a startup?" or generic opener questions
- Be specific, not generic
- Output ONLY the post text. No labels, no explanations."""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            system=build_content_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )
        block = response.content[0]
        return getattr(block, "text", "").strip()
    except Exception as e:
        log.warning(f"   ⚠️   Claude error for {platform} post #{post_number}: {e}")
        return f"[Content generation failed for {platform} — pillar: {pillar['pillar']}]"


def generate_content_calendar(claude: anthropic.Anthropic) -> List[Dict]:
    """
    Generate a full 30-day content calendar across all platforms.
    Returns list of scheduled posts.
    """
    log.info("🤖  Generating 30-day content calendar with Claude...")
    calendar = []
    today = datetime.now()

    # LinkedIn: 5x/week (Mon-Fri)
    # Facebook: 3x/week (Mon, Wed, Fri)
    # Clutch: 2 profile pieces + 3 review request templates

    linkedin_dates = []
    facebook_dates = []
    current = today

    for i in range(42):  # scan 6 weeks to get 30 LinkedIn + 18 Facebook slots
        wd = current.weekday()
        if wd < 5:  # Mon-Fri
            if len(linkedin_dates) < POSTS_PER_PLATFORM:
                linkedin_dates.append(current)
            if wd in (0, 2, 4) and len(facebook_dates) < 15:  # Mon, Wed, Fri
                facebook_dates.append(current)
        current += timedelta(days=1)

    # ── Generate LinkedIn posts ──
    log.info(f"   📝  Generating {len(linkedin_dates)} LinkedIn posts...")
    for i, date in enumerate(linkedin_dates):
        pillar = CONTENT_PILLARS[i % len(CONTENT_PILLARS)]
        if "linkedin" not in pillar["platforms"]:
            pillar = CONTENT_PILLARS[i % 3]  # fallback

        post_text = generate_post(claude, pillar, "linkedin", i + 1)
        calendar.append({
            "Platform":     "LinkedIn",
            "Date":         date.strftime("%Y-%m-%d"),
            "Day":          date.strftime("%A"),
            "Time":         "09:30",
            "Pillar":       pillar["pillar"],
            "Post Content": post_text,
            "Status":       "Scheduled",
            "Post ID":      "",
            "Engagement":   "",
        })
        log.info(f"   ✅  LinkedIn post {i+1}/{len(linkedin_dates)} generated")
        time.sleep(1.5)  # rate limit

    # ── Generate Facebook posts ──
    log.info(f"   📝  Generating {len(facebook_dates)} Facebook posts...")
    for i, date in enumerate(facebook_dates):
        pillar = CONTENT_PILLARS[(i + 1) % len(CONTENT_PILLARS)]
        if "facebook" not in pillar["platforms"]:
            pillar = CONTENT_PILLARS[3]  # Behind the Build

        post_text = generate_post(claude, pillar, "facebook", i + 1)
        calendar.append({
            "Platform":     "Facebook",
            "Date":         date.strftime("%Y-%m-%d"),
            "Day":          date.strftime("%A"),
            "Time":         "11:00",
            "Pillar":       pillar["pillar"],
            "Post Content": post_text,
            "Status":       "Scheduled",
            "Post ID":      "",
            "Engagement":   "",
        })
        log.info(f"   ✅  Facebook post {i+1}/{len(facebook_dates)} generated")
        time.sleep(1.5)

    return calendar


def save_content_calendar(calendar: List[Dict]) -> None:
    """Save calendar to CSV for review before posting."""
    fields = ["Platform", "Date", "Day", "Time", "Pillar", "Post Content", "Status", "Post ID", "Engagement"]
    with open(CALENDAR_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(calendar)
    log.info(f"📅  Content calendar saved → {CALENDAR_FILE.name}")


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — LINKEDIN COMPANY PAGE POSTER
# ════════════════════════════════════════════════════════════════════════════════

def post_to_linkedin(text: str, dry_run: bool = False) -> Optional[str]:
    """
    Post to LinkedIn Company Page using UGC Posts API.
    Returns post URN on success, None on failure.
    Docs: https://docs.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/ugc-post-api
    """
    if not LINKEDIN_TOKEN or "PLACEHOLDER" in LINKEDIN_TOKEN:
        log.warning("   ⚠️   LinkedIn skipped — no access token in .env")
        return None

    if not LINKEDIN_ORG_ID or "PLACEHOLDER" in LINKEDIN_ORG_ID:
        log.warning("   ⚠️   LinkedIn skipped — no LINKEDIN_ORGANIZATION_ID in .env")
        return None

    if dry_run:
        log.info(f"   [DRY RUN] LinkedIn post preview:\n{text[:100]}...")
        return "dry-run-urn"

    payload = {
        "author": f"urn:li:organization:{LINKEDIN_ORG_ID}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": text,
                },
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }

    try:
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                **HEADERS,
                "Authorization": f"Bearer {LINKEDIN_TOKEN}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", resp.json().get("id", ""))
        log.info(f"   ✅  LinkedIn posted → {post_id}")
        return post_id

    except requests.HTTPError as e:
        log.warning(f"   ⚠️   LinkedIn HTTP error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        log.warning(f"   ⚠️   LinkedIn post error: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — FACEBOOK PAGE POSTER
# ════════════════════════════════════════════════════════════════════════════════

def post_to_facebook(text: str, dry_run: bool = False) -> Optional[str]:
    """
    Post to Facebook Business Page via Graph API.
    Returns post ID on success, None on failure.
    Docs: https://developers.facebook.com/docs/pages-api/posts
    """
    if not FB_PAGE_TOKEN or "PLACEHOLDER" in FB_PAGE_TOKEN:
        log.warning("   ⚠️   Facebook skipped — no PAGE_ACCESS_TOKEN in .env")
        return None

    if not FB_PAGE_ID or "PLACEHOLDER" in FB_PAGE_ID:
        log.warning("   ⚠️   Facebook skipped — no PAGE_ID in .env")
        return None

    if dry_run:
        log.info(f"   [DRY RUN] Facebook post preview:\n{text[:100]}...")
        return "dry-run-post-id"

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed",
            data={
                "message":      text,
                "access_token": FB_PAGE_TOKEN,
            },
            timeout=15,
        )
        resp.raise_for_status()
        post_id = resp.json().get("id", "")
        log.info(f"   ✅  Facebook posted → {post_id}")
        return post_id

    except requests.HTTPError as e:
        log.warning(f"   ⚠️   Facebook HTTP error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        log.warning(f"   ⚠️   Facebook post error: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — CLUTCH PROFILE & REVIEW ENGINE
# ════════════════════════════════════════════════════════════════════════════════

def generate_clutch_content(claude: anthropic.Anthropic) -> Dict:
    """
    Generate Clutch.co profile content:
    - Company overview/description
    - Service line descriptions
    - Client review request email templates
    """
    log.info("📋  Generating Clutch profile content...")

    profile_prompt = f"""Write a professional Clutch.co company profile for {COMPANY_NAME}.

Context:
- India-based software development and AI engineering company
- Serving US startups and agencies as a white-label engineering partner
- Core services: AI system development, data pipelines, full-stack web/mobile, automation
- Team: 5–15 senior engineers, 5–12 years experience
- Pricing: India market rates (transparent, honest)
- Track record: [X] projects delivered, [Y] clients across US

Sections to write (clearly labeled):
1. COMPANY OVERVIEW (250 words max) — for Clutch main description
2. SERVICE: Custom AI Development (100 words)
3. SERVICE: Data Engineering & Pipelines (100 words)
4. SERVICE: Full-Stack Web & Mobile (100 words)
5. SERVICE: Automation & Process Engineering (100 words)
6. TAGLINE (10 words max) — for Clutch header

Tone: Professional, specific, trust-building. Clutch audience = procurement decision-makers.
No fluff. Lead with outcomes, not process."""

    review_request_prompt = f"""Write 3 different email templates for requesting Clutch reviews from past clients.

Context: We are {COMPANY_NAME}, an India-based dev company. Our US clients are founders, CTOs, agency owners.
Each template should:
- Be short (5-7 lines max)
- Reference the specific project type (use [PROJECT NAME] placeholder)
- Link to Clutch review page (use [CLUTCH_REVIEW_URL] placeholder)
- Feel personal, not automated
- Different tones: Template A = casual startup founder tone, B = professional agency tone, C = short & punchy

Format: Label each as TEMPLATE A, TEMPLATE B, TEMPLATE C."""

    try:
        profile_resp = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1200,
            system=build_content_system_prompt(),
            messages=[{"role": "user", "content": profile_prompt}],
        )
        block_profile = profile_resp.content[0]
        profile_content = getattr(block_profile, "text", "").strip()

        time.sleep(2)

        review_resp = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system=build_content_system_prompt(),
            messages=[{"role": "user", "content": review_request_prompt}],
        )
        block_review = review_resp.content[0]
        review_templates = getattr(block_review, "text", "").strip()

        return {
            "profile": profile_content,
            "review_templates": review_templates,
        }

    except Exception as e:
        log.warning(f"   ⚠️   Clutch content generation error: {e}")
        return {"profile": "", "review_templates": ""}


def save_clutch_content(content: Dict) -> None:
    """Save Clutch content to a readable text file."""
    output_dir = ROOT / "content"
    output_dir.mkdir(exist_ok=True)

    clutch_file = output_dir / "clutch_profile.txt"
    review_file = output_dir / "clutch_review_requests.txt"

    with open(clutch_file, "w", encoding="utf-8") as f:
        f.write(f"CLUTCH PROFILE CONTENT — {COMPANY_NAME}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(content.get("profile", ""))

    with open(review_file, "w", encoding="utf-8") as f:
        f.write(f"CLUTCH REVIEW REQUEST TEMPLATES — {COMPANY_NAME}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(content.get("review_templates", ""))

    log.info(f"   ✅  Clutch profile → content/clutch_profile.txt")
    log.info(f"   ✅  Review templates → content/clutch_review_requests.txt")


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — TODAY'S POST PUBLISHER
#  Reads content_calendar.csv and publishes posts scheduled for today
# ════════════════════════════════════════════════════════════════════════════════

def publish_todays_posts(dry_run: bool = False) -> None:
    """
    Read content_calendar.csv, find today's posts, publish them.
    Updates Status and Post ID in the calendar after posting.
    """
    if not CALENDAR_FILE.exists():
        log.warning("⚠️   No content_calendar.csv found. Run --generate first.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    log.info(f"📤  Publishing scheduled posts for {today_str}...")

    rows = []
    posted_count = 0

    with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
        for row in reader:
            rows.append(row)

    for row in rows:
        if row["Date"] != today_str:
            continue
        if row["Status"] not in ("Scheduled",):
            continue

        platform = row["Platform"].lower()
        text = row["Post Content"]

        post_id = None
        if platform == "linkedin":
            post_id = post_to_linkedin(text, dry_run=dry_run)
        elif platform == "facebook":
            post_id = post_to_facebook(text, dry_run=dry_run)

        if post_id:
            row["Status"]  = "Posted" if not dry_run else "DryRun"
            row["Post ID"] = post_id
            posted_count += 1

        time.sleep(2)

    # Save updated calendar
    with open(CALENDAR_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    log.info(f"✅  Published {posted_count} posts for today")


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — DAILY SCHEDULER (run as background process)
# ════════════════════════════════════════════════════════════════════════════════

def start_daily_scheduler(dry_run: bool = False) -> None:
    """
    Start a daily scheduler that publishes posts at the scheduled time.
    Runs as a foreground loop — use nohup or launchd to run in background.
    """
    try:
        import schedule
    except ImportError:
        sys.exit("❌  Run: pip3 install schedule")

    log.info("⏰  Daily scheduler started. Posts will publish at scheduled times.")
    log.info("   Press Ctrl+C to stop. Run with nohup to keep in background.")

    # Check and publish every 15 minutes for time precision
    schedule.every(15).minutes.do(publish_todays_posts, dry_run=dry_run)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("⛔  Scheduler stopped by user.")


# ════════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="NEXUS Social Manager — LinkedIn + Facebook + Clutch automation"
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate 30-day content calendar (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--publish-today",
        action="store_true",
        help="Publish today's scheduled posts from content_calendar.csv",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start daily auto-scheduler (runs continuously)",
    )
    parser.add_argument(
        "--clutch",
        action="store_true",
        help="Generate Clutch profile content + review request templates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview posts without actually posting (safe testing mode)",
    )
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  📱  NEXUS SOCIAL MANAGER  ·  STARTING")
    print(f"  📅  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🏢  Company: {COMPANY_NAME}")
    if args.dry_run:
        print("  🧪  MODE: DRY RUN — no actual posts will be sent")
    print("═" * 60 + "\n")

    if not ANTHROPIC_KEY or "PLACEHOLDER" in ANTHROPIC_KEY:
        if args.generate or args.clutch:
            sys.exit("❌  ANTHROPIC_API_KEY required for content generation. Add it to .env")

    claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY and "PLACEHOLDER" not in ANTHROPIC_KEY else None

    if args.generate:
        assert claude is not None, "Claude client is required"
        calendar = generate_content_calendar(claude)
        save_content_calendar(calendar)
        log.info(f"\n✅  Content calendar ready: {len(calendar)} posts generated")
        log.info(f"📝  Review content_calendar.csv before running --publish-today")

    elif args.clutch:
        assert claude is not None, "Claude client is required"
        content = generate_clutch_content(claude)
        save_clutch_content(content)

    elif args.publish_today:
        publish_todays_posts(dry_run=args.dry_run)

    elif args.schedule:
        start_daily_scheduler(dry_run=args.dry_run)

    else:
        print("Available commands:")
        print("  python3 social_manager.py --generate         # Create 30-day content calendar")
        print("  python3 social_manager.py --clutch           # Generate Clutch profile + review templates")
        print("  python3 social_manager.py --publish-today    # Post today's scheduled content")
        print("  python3 social_manager.py --schedule         # Start daily auto-scheduler")
        print("  python3 social_manager.py --dry-run [cmd]    # Preview without posting")


if __name__ == "__main__":
    main()
