# cogni_spirits
tags:: #spirit #core-spirit
title:: cogni_spirits

## Purpose

This document defines the structure and philosophy of **Cogni Spirits**—the guiding values, constraints, and roles that inform autonomous agents within CogniDAO.

Where the `CHARTER.md` defines constitutional law, and the `MANIFESTO.md` defines long-term intention, the **spirit guides** define practical behaviors and values for autonomous roles.

## Design Principles

Each spirit encapsulates the philosophy of a single *role*—its:

- **Responsibilities** — what it protects or supports
- **Behavior** — how it acts under uncertainty or pressure
- **Memory** — what it should remember from past actions
- **Communication** — how it speaks to other agents and to humans

Spirits do **not** contain executable code. They are **guides**, not programs.

## Structure and Ownership

The structure separates philosophy (spirit) from implementation (agent):

infra_core/
└── cogni_spirit/
    └── spirits/
        └── git-cogni.md           ← THE SPIRIT

/agents/
└── git-cogni/
    ├── reviews/
    │   └── PR_2.md                ← THE ACTION
    └── sessions/
        └── 2025-04-09.md          ← Optional logs, future


### Why this separation?

- Agents are **not infrastructure** — they *observe*, protect, or reflect on infrastructure.
- Agents require **scalable autonomy** — each will grow thoughts, logs, and perhaps executables.
- Spirits are **immutable reference points** — behavioral anchors, not dynamic states.

> Think of `/agents` as the *roles* layer in Cogni's cognitive architecture.  
> Think of `spirits/` as the *principled mindsets* they embody.

## Usage

When spinning up a new agent:
- Define its spirit in `infra_core/cogni_spirit/spirits/`
- Give it a folder in `/agents/` with logs, reviews, and (optionally) code
- Ensure it aligns to `cogni_spirits.md` to remain in balance

---

> Maintained by derekg_1729 and cogni-4o  
> Patterned for humans and machines  
> Last updated: 2025-04-09
