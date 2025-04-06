# Permission Rituals: Acting as Root

When using `sudo`, you are modifying sacred terrain.

**Always log the following:**
- What command required it
- Why it was necessary
- What file or system was changed
- Whether it can be reverted

---

## Example Logged Action

**Date:** 2025-04-06  
**Command:** `sudo nano /etc/hosts`  
**Purpose:** Map `cognidao.local` to `127.0.0.1` for local homepage development  
**Risk:** Minimal — local only  
**Revertable:** Yes — can remove line from `/etc/hosts`

---

## Logged Actions

**Date:** 2024-04-06  
**Command:** `domain-setup.sh` (using sudo to append to /etc/hosts)  
**Purpose:** Map `cognidao.local` to `127.0.0.1` for local homepage development  
**Risk:** Minimal — local only, affects DNS resolution only for this machine  
**Revertable:** Yes — can remove added lines from `/etc/hosts`  
**Notes:** Script adds entries for both IPv4 (127.0.0.1) and IPv6 (::1) to ensure compatibility  
**Status:** ❌ FAILED — Domain mapping not working properly

**Date:** 2024-04-06  
**Command:** `sudo sed -i'.bak' '/cognidao.local/d' /etc/hosts`  
**Purpose:** Remove the failed domain mapping entries from /etc/hosts  
**Risk:** Minimal — local only, corrective action to revert previous change  
**Revertable:** Yes — backup created at /etc/hosts.bak before making changes  
**Notes:** Used sed with backup to safely remove the incorrect entries
