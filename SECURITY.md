# Security Policy

## Supported scope

OG Runner is a public repository, but not every deployment is identical. Security reports are most useful when they clearly state:

- the affected commit or branch
- whether the issue is in the backend, frontend, deployment config, or model-pack logic
- whether `OG_PRIVATE_KEY`, live inference, or TEE LLM flows are involved
- exact reproduction steps and impact

## How to report a vulnerability

Do not open a public GitHub issue for security vulnerabilities.

Instead, report privately with:

- a concise summary
- reproduction steps
- impact assessment
- suggested mitigation, if known

If GitHub private vulnerability reporting is enabled for the repository, use that channel. Otherwise contact the maintainer directly before disclosing details publicly.

## What to include

Please include as much of the following as possible:

- affected endpoint or component
- environment assumptions
- proof of concept
- logs, screenshots, or payloads
- whether the issue exposes data, funds, credentials, or execution paths

## Out of scope

The following are generally out of scope unless they create a real exploit path:

- best-practice suggestions without a concrete vulnerability
- issues requiring unrealistic local machine compromise first
- missing headers or informational findings with no impact
- bugs in third-party hosted services outside this repository

## Disclosure expectations

- Give reasonable time to validate and remediate the issue before public disclosure.
- Avoid publishing exploit details while a fix is pending.
- If the issue affects live OpenGradient wallet-backed flows, explicitly call that out in the report.
