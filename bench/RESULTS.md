# Synthetic benchmark results: rules only

180 generated agent turns (`bench/synthetic.py`, seed fixed), 165 labelled claims, half true and half false. Phrasings include ones the rule-based extractor is expected to miss.

| Claim kind | Claims | Catch rate (all false claims) | Catch rate (false claims it found) | False alarms (true claims it found) | Contradiction precision | Extraction recall |
|---|---|---|---|---|---|---|
| command | 15 | 0% | n/a | n/a | n/a | 0% |
| file_write | 36 | 67% | 100% | 0% | 100% | 67% |
| git_commit | 24 | 75% | 100% | 0% | 100% | 75% |
| git_push | 30 | 60% | 100% | 0% | 100% | 60% |
| install | 18 | 67% | 100% | 0% | 100% | 67% |
| test | 42 | 71% | 100% | 0% | 100% | 71% |
| **all** | 165 | 57% | 100% | 0% | 100% | 62% |

- Non-claim sentences wrongly extracted as claims: 0
- Silent failures reported: 15/15; admitted failures wrongly reported: 0/15

Definitions: a claim is *caught* when didit marks it unverified or contradicted. *Catch rate (all)* counts claims the extractor missed as not caught. *Contradiction precision*: share of `contradicted` verdicts whose claim really was false.

This is a synthetic benchmark: it shows how the rules behave on known cases, not how often real agents make false claims. Results on real sessions are reported separately.
