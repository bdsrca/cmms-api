# Multi-Agent Roadmap

The first version of the API can work with a single model call and deterministic validation.

The future version can use multiple small agents when the decision becomes more complex.

## Why multi-agent fits CMMS/EAM

Maintenance decisions combine several types of knowledge:

- what the user said;
- where the problem is;
- which asset may be involved;
- how urgent it is;
- what trade should handle it;
- what safety rules apply;
- whether similar work happened before;
- whether parts or scheduling constraints matter.

One huge prompt can mix these concerns together. A multi-agent design keeps them separate and reviewable.

## Proposed agents

| Agent | Output |
| --- | --- |
| Intake Agent | Clean summary and symptom classification. |
| Location Agent | Building, area, room, and confidence. |
| Asset Agent | Candidate assets and match evidence. |
| Priority Agent | Priority suggestion and reasoning. |
| Policy Agent | Automation boundary and safety warnings. |
| Parts Agent | Likely materials and planning hints. |
| Scheduling Agent | Queue, trade, and follow-up suggestion. |
| Analytics Agent | Similar failures, repeat calls, trend signals. |

## Debate and merge step

Agents should not blindly vote. The merge step should look for conflicts:

- Location Agent says the room is unknown.
- Asset Agent finds three possible assets.
- Priority Agent suggests urgent.
- Policy Agent says urgent requests require dispatcher review.

The final response should explain the conflict and ask for review instead of forcing a fake answer.
