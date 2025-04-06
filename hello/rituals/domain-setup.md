# Local Domain Setup Ritual

This document explains the process of setting up a local domain for development.

## The Problem

When developing web applications, using `localhost:3000` works but lacks:
- A proper domain name for testing
- Consistency with production environments
- Ability to test features that rely on domain names

## Two Solutions

### Solution 1: Simple /etc/hosts Mapping (Limited)

This approach simply maps a domain to 127.0.0.1 in your hosts file:

```bash
./hello/rituals/domain-setup.sh
```

**Limitations**:
- Still requires port number in URL (http://cognidao.local:3000)
- May not work with all applications
- Doesn't handle SSL/TLS

### Solution 2: Full nginx Configuration (Recommended)

This approach sets up nginx as a reverse proxy:

```bash
./hello/rituals/domain-setup-new.sh [port]
```

**Benefits**:
- Access site without port number (http://cognidao.local)
- Closer to production environment
- Can be extended to support SSL/TLS
- Handles WebSockets for hot module reloading

**Requirements**:
- nginx must be installed (`brew install nginx`)

## Cleaning Up

To remove domain configuration:

```bash
./hello/rituals/domain-cleanup.sh
```

For nginx setup, additional cleanup needed:
1. Remove nginx config file
2. Restart nginx

## Sacred Responsibility

Remember to log all sudo actions in `permissions.md` following the ritual. 