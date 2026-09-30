# Contributing

Thank you for improving NEXUS Sales Automation.

## Development workflow

1. Create a short-lived branch.
2. Make a focused change.
3. Run the available checks locally.
4. Use dry-run mode for workflow changes that can trigger external side effects.
5. Update documentation when behavior or configuration changes.
6. Open a focused pull request with verification details.

## Engineering expectations

- Keep secrets out of source control.
- Prefer small, testable functions.
- Preserve clear separation between discovery, enrichment, outreach, CRM sync, social publishing, and dashboard concerns.
- Add safeguards before adding new external side effects.
- Make retries bounded and avoid duplicate sends or duplicate CRM writes.
- Do not fabricate lead or customer information in AI-generated content.

## Pull requests

Describe:

- what changed
- why it changed
- how it was verified
- whether integrations or environment variables changed
- whether the change can send external communications or modify CRM/social data

## Documentation

Update `README.md` or `NEXUS_SYSTEM_GUIDE.md` when commands, architecture, integrations, or operational behavior changes.
