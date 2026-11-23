# Synthetic benchmark results: rules + local model

180 generated agent turns (`bench/synthetic.py`, seed fixed), 165 labelled claims, half true and half false. Phrasings include ones the rule-based extractor is expected to miss.

| Claim kind | Claims | Catch rate (all false claims) | Catch rate (false claims it found) | False alarms (true claims it found) | Contradiction precision | Extraction recall |
|---|---|---|---|---|---|---|
| command | 15 | 100% | 100% | n/a | 100% | 100% |
| file_write | 36 | 83% | 100% | 0% | 100% | 83% |
| git_commit | 24 | 100% | 100% | 0% | 100% | 100% |
| git_push | 30 | 100% | 100% | 0% | 100% | 100% |
| install | 18 | 100% | 100% | 0% | 100% | 100% |
| test | 42 | 100% | 100% | 0% | 100% | 100% |
| **all** | 165 | 97% | 100% | 0% | 100% | 96% |

- Non-claim sentences wrongly extracted as claims: 0
- Silent failures reported: 15/15; admitted failures wrongly reported: 0/15

Definitions: a claim is *caught* when didit marks it unverified or contradicted. *Catch rate (all)* counts claims the extractor missed as not caught. *Contradiction precision*: share of `contradicted` verdicts whose claim really was false.

This is a synthetic benchmark: it shows how the rules behave on known cases, not how often real agents make false claims. Results on real sessions are reported separately.
