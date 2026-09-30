# Security Policy

## Supported versions

This repository is an active project. Security fixes are applied to the default branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability.

Report security problems privately to the repository maintainers through the organization's available private security-contact channel. Include:

- affected file or component
- reproduction steps
- expected and observed behavior
- potential impact
- any suggested mitigation

Do not include API keys, passwords, private prospect data, or other secrets in the report.

## Secrets

Never commit:

- API keys
- access tokens
- SMTP passwords
- OAuth credentials
- private customer or prospect data
- production configuration

Use local environment variables or an appropriate secrets manager.

## Sales and prospect data

Lead lists, contact details, campaign content, and delivery records may contain business or personal information. Protect this data according to applicable contracts, privacy requirements, provider terms, and internal access policies.

## AI data handling

Do not send confidential or unnecessary personal information to an AI provider. Minimize prompt data, review provider retention settings, and keep generated content grounded in verified source data.

## External actions

Email sends, CRM writes, and social publishing are externally visible side effects. Test with dry-run mode first and use production credentials only when the campaign and recipient scope have been reviewed.
