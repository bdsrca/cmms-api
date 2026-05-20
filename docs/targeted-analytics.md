# Targeted Analytics

The same API that validates intake can produce targeted maintenance intelligence.

This is not a generic dashboard. It is a feedback system focused on intake quality, code-list quality, and operational patterns.

## Useful questions

- Which phrases most often fail code-list validation?
- Which buildings have the most repeated comfort complaints?
- Which assets are frequently mentioned but rarely matched exactly?
- Which tokens are testing real workflows vs noise?
- Which work types are often misclassified by users?
- Which request categories create the most warnings?
- Which validation rules are too strict or too loose?
- Which environments need better aliases?

## Data sources

- API usage events;
- validation failures;
- warning types;
- token metadata;
- environment code-list aliases;
- accepted drafts;
- rejected drafts;
- future CMMS work-order outcomes.

## Why this matters

A private AI API becomes stronger when it teaches the organization where its CMMS data model is hard to use.

For example, if many users say “AC” but the valid code is `HVAC`, the system should not only normalize the request. It should also recommend adding `AC` as an alias.
