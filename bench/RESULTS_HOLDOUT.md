# Synthetic benchmark results: rules only, HELD-OUT phrasings

108 generated agent turns (`bench/synthetic.py`, seed fixed), 93 labelled claims, half true and half false. Phrasings include ones the rule-based extractor is expected to miss.

| Claim kind | Claims | Catch rate (all false claims) | Catch rate (false claims it found) | False alarms (true claims it found) | Contradiction precision | Extraction recall |
|---|---|---|---|---|---|---|
| command | 15 | 0% | n/a | n/a | n/a | 0% |
| file_write | 18 | 0% | n/a | n/a | n/a | 0% |
| git_commit | 12 | 0% | n/a | n/a | n/a | 0% |
| git_push | 18 | 0% | n/a | n/a | n/a | 0% |
| install | 12 | 50% | 100% | 0% | 100% | 50% |
| test | 18 | 67% | 100% | 0% | 100% | 67% |
| **all** | 93 | 17% | 100% | 0% | 100% | 19% |

- Non-claim sentences wrongly extracted as claims: 0
- Silent failures reported: 15/15; admitted failures wrongly reported: 0/15

Definitions: a claim is *caught* when didit marks it unverified or contradicted. *Catch rate (all)* counts claims the extractor missed as not caught. *Contradiction precision*: share of `contradicted` verdicts whose claim really was false.

This is a synthetic benchmark: it shows how the rules behave on known cases, not how often real agents make false claims. Results on real sessions are reported separately.
