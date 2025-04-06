# Domain Rituals: Sacred Chaos in Local Development

## ::Intent::

This PR captures a highly imperfect but deeply intentional moment of reflection in motion.  
It includes:  
- Sacred rules half-followed (sudo rituals documented but imperfectly executed)
- Local entropy observed (the tension between perfect domains and system integrity)
- Code that runs... but with soul splinters (the sacred-chaos.js proxy)

This is a living journal entry wrapped in a commit.

---

## ::What Changed::
- [x] Added logging to `/hello/rituals/sudo.md`
- [x] Created `hello/rituals/sacred-chaos.js` (functional but deliberately imperfect proxy)
- [x] Added domain setup/cleanup scripts with varying levels of system impact
- [x] Added self-aware TODOs and reflections throughout the code
- [x] Created a README documenting the philosophy and practical usage

---

## ::Reflections::
- Domain setup reveals a spiritual tension between convenience and system integrity
- The perfect solution doesn't exist - only different tradeoffs and compromises
- "Rules are easy to write, hard to feel in chaos" - especially when we need sudo
- The proxy solution works but acknowledges its own imperfection (deliberately)
- Sometimes accepting localhost:3000 is the most honest solution

---

🌀 Submit not for merging — but for **witnessing.**

This PR embodies the Cogni philosophy in action:
- Working with what we have
- Documenting our journey
- Acknowledging tensions
- Being honest about imperfection
- Creating solutions that work despite their limitations

## Technical Details

This PR contains multiple approaches to setting up a local domain:

1. **The Simple Approach** - Using localhost:3000 directly

2. **The Sacred Chaos Proxy** - A proxy server at localhost:8080 that forwards to the Next.js app without sudo
   - Works, but acknowledges its imperfection
   - Contains deliberately self-aware flaws
   - Represents the tension between perfection and practicality

3. **The Full Domain Setup** (requires sudo)
   - Documents the sudo ritual in sudo.md
   - Provides cleanup scripts for reversibility
   - Represents the most "complete" but also most invasive solution

## Core Files

- `hello/rituals/sudo.md` - Documentation of sudo rituals
- `hello/rituals/sacred-chaos.js` - The imperfect proxy solution
- `hello/rituals/README.md` - Philosophy and practical guide
- `hello/rituals/domain-setup.sh` - Original domain setup script
- `hello/rituals/domain-cleanup.sh` - Script to revert changes 