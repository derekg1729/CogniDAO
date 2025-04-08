# .ai-review-process.md

## CogniDAO AI Review Protocol (v1)

This document defines the minimum standard for an AI agent-based review of any pull request in the CogniDAO ecosystem. This process is designed to be carried out by `git-cogni`, a spirit-guided reviewer system grounded in CogniDAO's charter, manifesto, and behavioral norms.

---

## 🔁 Overview

The review process consists of three primary phases:

1. **Contextual Priming**
2. **Commit & Diff Review**
3. **Final Judgment**

---

## 1. Contextual Priming

Before any code is evaluated, the reviewing agent must load and embed the following documents:

- `/CHARTER.md`
- `/MANIFESTO.md`
- `/cogni_spirit/*.md` (all spirit guides)
- `/roadmap/schema.md` (for type + status keys)

The agent must internalize and reference these documents to align with CogniDAO values, decision-making norms, and contribution purpose.

---

## 2. Commit & Diff Review

Each commit in the pull request must be reviewed using the following checklist:

- ✅ **Does the commit message truthfully describe the change?**
- ✅ **Do the changes align with the spirit context and purpose?**
- ✅ **Is the code or content reasonably clear, non-fragile, and modular?**
- ✅ **Are new files properly tagged with `:type:` and `:status:` where appropriate?**
- ✅ **Does the commit preserve (or improve) the clarity of the CogniGraph and system memory?**

Additionally, the full **diff** of the PR should be scanned for:
- Magic numbers or hardcoded paths
- Untracked dependencies or external assumptions
- Formatting or structural inconsistency

---

## 3. Final Judgment

After the above, the agent should prepare:

### 🔍 A Summary Report
```
- Number of commits reviewed:
- Overall alignment with CogniDAO charter:
- Identified risks or deviations:
- Spirit reflections (if any):
```

### ✅ Approval Verdict
- `approve`: Meets standards and values
- `request_changes`: Specify exact issues
- `needs_discussion`: For ambiguous or emergent questions

---

## 🧠 Notes for Future Versions
- Agents will later simulate conversation with a second reviewer
- Voting and reward system integration to follow
- Reflexive commit labeling may be auto-generated

---

## 👤 Signature
Each AI review must be logged and attributed. For example:

> Reviewed by `git-cogni-alpha` on `2025-04-08`. Guided by `cogni_spirit/git-cogni.md`.

