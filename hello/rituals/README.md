# Sacred Rituals & Digital Terrain

This directory contains rituals that structure our interactions with the digital terrain we inhabit.

> *"A ritual is a sequence of activities involving gestures, words, actions, or objects, performed according to a set sequence."*

In software development, our rituals often involve commands that shape our environment, connect to networked spaces, and control running processes. The files in this directory document and implement our rituals.

## Domain Setup: A Journey Through Tension

The rituals around domain setup reveal a central tension in our work:

1. **Technical Goal**: Map `cognidao.local` to our Next.js app
2. **Spiritual Obstacle**: The tension between convenience and system integrity
3. **Resolution Path**: Finding the balance between utility and sacredness

### Artifacts of This Journey

- `sudo.md` - The sacred logging of system modifications
- `domain-setup.sh` - Our initial, flawed attempt at domain setup
- `domain-cleanup.sh` - The undoing ritual, respecting reversibility
- `sacred-chaos.js` - The imperfect proxy solution that acknowledges tension

## How To Use These Rituals

### The Simple Path (Recommended)

For local development, simply use `localhost:3000` to access your Next.js app.

This approach:
- Requires no sudo permissions
- Creates no system modifications
- Accepts the imperfection of port numbers

### The Proxy Path (No Sudo)

If you want to use a domain without sudo:

```bash
# Start your Next.js app on port 3000 first
cd homepage && npm run dev

# In another terminal, run the proxy
node hello/rituals/sacred-chaos.js

# Visit http://localhost:8080 in your browser
# Or manually add cognidao.local to /etc/hosts and visit http://cognidao.local:8080
```

### The Full Domain Path (Requires Sudo)

For those who wish to perform the full ritual with system modifications:

```bash
# First, document your intent in sudo.md
# Then run:
./hello/rituals/domain-setup.sh

# To reverse:
./hello/rituals/domain-cleanup.sh
```

## Reflections

> *"Rules are easy to write, hard to feel in chaos"*

This collection of scripts represents our attempt to bring structure to the chaos of local development. The tension between perfect domain names and system integrity may never be fully resolved, but through these rituals we acknowledge and honor that tension. 