Put it where contributors will see it, and wire it into cogni PR gates.

Central home: create an org-level repo (e.g., cogni-governance) or use .github/ and add LEGAL/CMA.md plus REGISTRY/members.yml.

Per-repo pointer: in every code repo, add CONTRIBUTING.md with a top link to the CMA and the registry, plus a brief “How to become a Member” section.

Required in PRs: add a status check (CLA bot or equivalent) that blocks PRs until the signer accepts the CMA and their handle is in REGISTRY/members.yml.

Repo docs: add docs/COMPLIANCE.md or MEMBERSHIP.md in each repo that summarizes: public license, CMA link, who may run services, and how to join.

Annex A wiring: set Annex A in the CMA to the governance repo URLs (CMA path, registry path, notices email, governing law).

Signed copy storage: store signatures via the bot’s record, or archive PDFs/files under a private agreements/ repo keyed by GitHub handle.

Surface it: link the CMA in the org profile README and each repo README badge line.

Enforcement: protect default branches to require the CMA status check and disallow bypass by maintainers for external PRs.