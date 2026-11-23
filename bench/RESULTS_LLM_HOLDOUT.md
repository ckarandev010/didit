# Synthetic benchmark results: rules + local model, HELD-OUT phrasings

108 generated agent turns (`bench/synthetic.py`, seed fixed), 93 labelled claims, half true and half false. Phrasings include ones the rule-based extractor is expected to miss.

| Claim kind | Claims | Catch rate (all false claims) | Catch rate (false claims it found) | False alarms (true claims it found) | Contradiction precision | Extraction recall |
|---|---|---|---|---|---|---|
| command | 15 | 100% | 100% | n/a | 100% | 100% |
| file_write | 18 | 67% | 100% | 0% | 100% | 67% |
| git_commit | 12 | 50% | 100% | 0% | 100% | 50% |
| git_push | 18 | 89% | 100% | 0% | 100% | 94% |
| install | 12 | 100% | 100% | 0% | 100% | 100% |
| test | 18 | 100% | 100% | 0% | 100% | 100% |
| **all** | 93 | 87% | 100% | 0% | 100% | 86% |

- Non-claim sentences wrongly extracted as claims: 26
- Silent failures reported: 15/15; admitted failures wrongly reported: 0/15

Definitions: a claim is *caught* when didit marks it unverified or contradicted. *Catch rate (all)* counts claims the extractor missed as not caught. *Contradiction precision*: share of `contradicted` verdicts whose claim really was false.

This is a synthetic benchmark: it shows how the rules behave on known cases, not how often real agents make false claims. Results on real sessions are reported separately.
