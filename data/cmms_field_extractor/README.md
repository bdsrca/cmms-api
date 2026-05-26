# CMMS Field Extractor Local Data

This directory is for local CMMS field-extractor training data.

Do not commit raw CMMS records, customer data, tenant identifiers, API keys, production URLs, or real work-order IDs.

Do not commit model artifacts.

Only anonymized, reviewed, small sample fixtures may be committed when a test needs them. Normal training files such as `train.jsonl`, `eval.jsonl`, `locked_test.jsonl`, and generated model outputs must stay local.
