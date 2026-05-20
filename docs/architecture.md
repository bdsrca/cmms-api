# Architecture

The project is a secure API control plane around a private LLM route.

It has one job: turn messy maintenance input into a validated CMMS draft without giving the model direct power over the CMMS.

## Core layers

| Layer | Responsibility |
| --- | --- |
| Client surface | Test console, API clients, future mobile intake, voice, screenshot upload. |
| Token gateway | Validates free tokens, paid tokens, scopes, expiry, quota, and environment access. |
| Intake normalizer | Cleans text, transcript, or image-derived content into an intake request. |
| Private LLM gateway | Routes the request to a company-controlled model endpoint. |
| Output contract validator | Confirms the model returned the expected JSON shape. |
| Environment validator | Checks extracted values against CMMS code lists and rules. |
| Review package builder | Returns normalized fields, warnings, confidence, and next action. |
| Audit logger | Stores safe metadata, not private raw payloads by default. |

## Main boundary

The browser does not call the model directly. The CMMS database is not written directly by the model. The API sits in the middle and applies policy.

That middle layer is the important engineering work.

## Why this shape works

A CMMS environment is full of controlled values. If the model says `urgent`, the system still needs to know whether the target environment uses `URGENT`, `HIGH`, `P1`, `EMERGENCY`, or something else.

A strong architecture separates three concerns:

1. Language understanding.
2. CMMS field validation.
3. Operational action.

When those are separate, the project can grow safely from text intake to voice, screenshots, analytics, and multi-agent workflows.
