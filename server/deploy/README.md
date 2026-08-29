# PocketClot — Production Deployment

This is how you get PocketClot **permanently online** on a mini-PC (or any
Linux host), with a **stable URL** that survives every reboot.

**Default path: Tailscale Funnel.** Persistent `*.ts.net` URL, no domain
required, free, auto-HTTPS, no port forwarding.

---

## TL;DR

```bash
# 1. On the mini-PC: one-shot install
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash

# 2. Log in to Claude (one-time)
sudo -u pocket-claude -H claude login

# 3. Set up the tunnel — default is Tailscale Funnel
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh

# 4. (optional) Migrate data from a Mac
# On the MAC, inside the PocketClaude repo, in the server/ subdir:
./deploy/migrate-to-server.sh me@your-host    # Tailscale name is enough
```

After that, PocketClot runs **always**, even after reboot, power outage, or
update. The URL is persistent — enter it in the app once and never touch it
again.

**Power-user alternative:** Cloudflare Named Tunnel with your own domain (see
below).

---

## Architecture

```
   PocketClot App (Android)
            │
            │  HTTPS — fixed URL, e.g. https://<host>.<tailnet>.ts.net
            ▼
   Tailscale Edge  (Funnel)
            │
            │  Tunnel (outbound from the mini-PC, no port forwarding)
            ▼
   Mini-PC (Ubuntu / Debian / Fedora)
   ├─ systemd service: pocket-claude.service
   │   └─ /opt/pocket-claude/.venv/bin/python -m pocket_claude
   │       (FastAPI + uvicorn on localhost:8787)
   └─ systemd service: tailscaled.service
       (with `tailscale funnel` enabled)
```

**Why this setup?**

- **systemd** = auto-start at boot, auto-restart on crash, logs in
  `journalctl`, no babysitter GUI needed.
- **Tailscale Funnel** = persistent URL of the form `<host>.<tailnet>.ts.net`,
  auto-HTTPS via Let's Encrypt, free on the Free plan (50 GB of public
  bandwidth per month — for a personal chat app, easily 100x oversized).
  No DNS setup, no port forwarding, NAT traversal built in.
- **Cloudflare Named Tunnel** (alternative) = persistent subdomain under your
  own Cloudflare-managed domain. Use this if you already have a domain there
  and want more control (e.g. putting Cloudflare Access in front of the app).
  Higher setup cost.
- **Service user `pocket-claude`** with restricted privileges: no escalation
  paths if the server is compromised.

---

## Step by step

### Step 1: Prepare the Linux mini-PC

Fresh Ubuntu Server / Desktop or Debian. Make sure SSH access works (this
makes later migration from a Mac easier):

```bash
# On the Mac (one-time)
ssh-copy-id user@your-host.local
```

### Step 2: Install PocketClot

On the mini-PC:

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

The script is **idempotent** — you can run it as often as you want without
breaking anything. It does:

| Step | What happens |
|---|---|
| 1 | Install Python 3, Node 20, git, curl |
| 2 | Create the `pocket-claude` user (service account) |
| 3 | Clone the repo to `/opt/pocket-claude` |
| 4 | Python venv + dependencies |
| 5 | Install the `claude` CLI via `npm install -g @anthropic-ai/claude-code` |
| 6 | Generate `.env` with a random `SERVER_TOKEN` |
| 7 | Install and enable `pocket-claude.service` (systemd) |

After the script finishes, the service is **not yet running**, because
`claude` has not been logged in.

### Step 3: Pick a Claude backend

PocketClot can talk to Claude through three different backends, switchable
per user inside the app (**Settings → Claude connection**):

| Backend | Setup needed on the server | Billing |
|---|---|---|
| **Pro/Max OAuth** (default) | `claude login` once | Your existing Claude Pro/Max subscription |
| **Anthropic API key** | Nothing — enter the `sk-ant-…` key in the app | Pay-as-you-go on the Anthropic Console account |
| **AWS Bedrock** | Nothing — enter AWS credentials in the app | Pay-as-you-go on your AWS account |

If you intend to use **only** the API-key or Bedrock path, you can skip the
OAuth login. Otherwise (recommended for most users), run:

```bash
sudo -u pocket-claude -H claude login
```

This opens a URL. Open it on another device (phone/Mac), sign in with your
Claude Pro/Max account, and paste the code back into the mini-PC terminal.

After that:

```bash
sudo systemctl restart pocket-claude
sudo systemctl status pocket-claude
```

It should show `active (running)`. Users who later add an Anthropic API key
or AWS credentials in the app's settings will use those instead of OAuth on
the next message — you don't need to redeploy.

### Step 4: Set up the tunnel

#### Default path: Tailscale Funnel

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

The script:
1. Checks whether Tailscale is running (if not: installs it + runs `tailscale up`)
2. Reads the mini-PC's FQDN from the tailnet (e.g. `<host>.<tailnet>.ts.net`)
3. Verifies that HTTPS certificate provisioning is enabled
4. Activates Funnel on port 443 → localhost:8787
5. Prints the URL you enter into the app

**Prerequisite (one-time in the tailnet admin):**

Go to <https://login.tailscale.com/admin/dns> and make sure:
- **MagicDNS** is enabled
- **HTTPS Certificates** is enabled

If not enabled yet, the script will direct you there and wait until you have
turned them on.

**Result:** a persistent URL like `https://<host>.<tailnet>.ts.net` — it
survives reboots, power outages, and Tailscale restarts.

Free plan limit: 50 GB of public bandwidth per month. A chat reply is a few
KB; even with audio readback and image generation you will not come anywhere
close in normal use.

#### Alternative: Cloudflare Named Tunnel (your own domain)

Use this only if you already have a domain managed at Cloudflare and want
more control (e.g. Cloudflare Access as an additional login layer in front
of the app).

```bash
sudo bash /opt/pocket-claude/deploy/setup-cloudflare-tunnel.sh
```

The script:
1. Installs `cloudflared`
2. Opens a browser login
3. Creates a named tunnel `pocket-claude`
4. Asks for the desired subdomain (e.g. `pocket-claude.your-domain.com`)
5. Creates the DNS record automatically
6. Installs `cloudflared` as a systemd service

### Step 5: App side

Open the PocketClot app:
1. **Add profile**
2. Server URL = your new tunnel URL from step 4
3. Username = `Admin`
4. Password = stored in `/opt/pocket-claude/data/INITIAL_PASSWORD.txt` on the mini-PC:
   ```bash
   sudo cat /opt/pocket-claude/data/INITIAL_PASSWORD.txt
   ```
5. Log in → the app forces a password change
6. Done.

---

## Migration from a Mac to the mini-PC

If you have been running PocketClot on a Mac and want to move it to the
mini-PC — no double setup needed.

**On the Mac** (inside the `server/` subdirectory of the PocketClaude repo):

```bash
# If Tailscale runs on both devices: just use the tailnet name
./deploy/migrate-to-server.sh me@your-host

# Without arguments: the script discovers the Linux node automatically via Tailscale
./deploy/migrate-to-server.sh
```

Or even easier: **double-click `Deploy to Mini-PC.command`** in the repo root —
interactive prompt, calls the migration script.

This transfers:

- `data/pocket_claude.db` — all chats, users, sessions
- `data/uploads/` — attachments
- `data/google_tts_credentials.json` — Cloud TTS service account (if present)
- `.env` — server token

On the mini-PC, the old data is **backed up beforehand** into
`data/.pre-migration-backup-<timestamp>/`, in case anything goes wrong.

**What is NOT migrated:**

- `~/.claude/credentials.json` — the Claude CLI login has to be redone
  (`sudo -u pocket-claude -H claude login` on the mini-PC). This is
  intentional: Claude sessions are often tied to device fingerprints.
- Cloudflare tunnel credentials — these are recreated on the mini-PC via
  `setup-cloudflare-tunnel.sh`. Advantage: the old Mac tunnel can stay
  around as a failover.

After the migration:

```bash
ssh user@your-host.local 'sudo systemctl status pocket-claude'
```

And in the app: switch the server URL to the mini-PC tunnel URL. Done.

---

## Maintenance

### Updates

```bash
sudo bash /opt/pocket-claude/deploy/helpers/update.sh
```

Runs `git pull` from GitHub, updates dependencies, restarts the service.

### Logs

```bash
# Server
journalctl -u pocket-claude -f

# Tunnel (default: Tailscale)
journalctl -u tailscaled -f
tailscale funnel status

# Tunnel (if using the Cloudflare path)
journalctl -u cloudflared -f
```

### Status

```bash
systemctl status pocket-claude
systemctl status cloudflared
```

### Manual restarts

```bash
sudo systemctl restart pocket-claude
sudo systemctl restart cloudflared
```

### Backup

Built into the server itself — the admin user can export an encrypted ZIP
from the app via *Settings → Back up data → Chat backup*. Recommended:
periodically save that ZIP somewhere (rsync to a NAS, cloud storage, etc.).

Alternatively, directly from the mini-PC:

```bash
sudo cp /opt/pocket-claude/data/pocket_claude.db ~/pocket-claude-backup-$(date +%Y%m%d).db
```

### Uninstall

```bash
sudo bash /opt/pocket-claude/deploy/helpers/uninstall.sh
```

Stops the services, archives data as a tar.gz, deletes everything. The data
backup ends up at `~/pocket-claude-backup-<TS>.tar.gz`.

---

## Troubleshooting

### "Server not running / 502 in the app"

```bash
# 1. Is the server actually running?
sudo systemctl status pocket-claude

# 2. If not, what do the logs say?
journalctl -u pocket-claude -n 100 --no-pager
```

Most common causes:
- `claude login` missing for the service user
- `.env` has wrong values
- Port 8787 is taken by another process

### "Tunnel down, but the server is running"

**For Tailscale Funnel:**
```bash
tailscale funnel status              # shows active routes + public URL
tailscale status                     # shows tailnet connectivity
journalctl -u tailscaled -n 100 --no-pager
```

Most common causes:
- HTTPS Certificates / MagicDNS disabled in the tailnet admin
- Funnel turned off after reboot → re-run `tailscale funnel --bg 443 on`
- ACL tags forbid Funnel — check the Tailscale admin → ACL

**For the Cloudflare path:**
```bash
sudo systemctl status cloudflared
journalctl -u cloudflared -n 100 --no-pager
```

Most common causes:
- Internet outage (cloudflared retries automatically)
- Credentials deleted from `/etc/cloudflared/`
- Tunnel manually disabled in the Cloudflare dashboard

### "Claude does not answer / rate limit"

That is on the Claude CLI / Anthropic side, not PocketClot. Check:

```bash
sudo -u pocket-claude -H claude -p "Test"
```

If that also fails: check your subscription status at claude.com, and re-run
`claude login` if needed.

### "Migration from the Mac fails"

- SSH access working? `ssh user@your-host.local 'echo OK'`
- PocketClot installed on the mini-PC? `ssh ... 'ls /opt/pocket-claude'`
- Passwordless `sudo`? If not, edit `sudoers` once or enter the password by
  hand (the migration script prompts).

### "Chat hangs / journal shows `Control request timeout: initialize`"

This is **NOT** a normal SDK timeout — it's the Claude CLI silently failing
to read its OAuth credentials because the systemd sandbox has masked
`/home/pocket-claude`. The unit file in this repo already has the fix, but
if you wrote your own systemd unit (or copied an old example), make sure
**`ProtectHome=true` is NOT set**:

```bash
# Inspect the unit file
sudo systemctl cat pocket-claude | grep -i protecthome

# If ProtectHome=true appears, drop it:
sudo sed -i '/^ProtectHome=true/d' /etc/systemd/system/pocket-claude.service
sudo systemctl daemon-reload
sudo systemctl restart pocket-claude
```

Background: `ReadWritePaths=/home/<service-user>` does NOT undo
`ProtectHome=true` — it only widens write permissions on a directory that's
already been masked. The CLI sees an empty home dir, can't find its
credential file, and silently hangs in the SDK handshake.

The other hardening flags (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`,
`ProtectKernelTunables/Modules/ControlGroups`) are all verified safe and
should stay enabled.

### "Chat reply comes back empty / 'No response requested.'"

The Claude Code CLI has an internal "skip turn" optimization for agentic
runs that sometimes fires on bare user statements ("I'll have a coffee").
PocketClot detects this and surfaces an error to the app so you don't
see a silent empty bubble.

The app's bundled system prompt explicitly forbids skip-turn replies, so
this should never fire in practice. If you wrote a **custom system prompt**
in the app and the CLI starts producing empty replies, add this line to
your custom prompt:

> Every user message expects a substantive reply. Never reply with "No
> response requested." or similar skip-turn placeholders.

### "Server stack-traces with `AssertionError` in `staticfiles.py:91`"

Browser DevTools or a stale service worker is trying to upgrade a request
on `/` to a WebSocket. Static files only handle HTTP. We already wrap
`StaticFiles` in `_HttpOnlyStaticFiles` to drop those silently, so this
should not appear after `v0.2.0`. If it does, you may be running an older
deploy — pull the latest `pocket_claude/server.py`.

### "SDK times out after a pip upgrade"

The Python SDK ships with a bundled `claude` binary in its `_bundled/`
directory that's sometimes older than what your system has. Bug #922
upstream. Workaround:

```bash
sudo ln -sf "$(command -v claude)" \
  /opt/pocket-claude/.venv/lib/python3.12/site-packages/claude_agent_sdk/_bundled/claude
sudo systemctl restart pocket-claude
```

(Replace `python3.12` with whatever venv Python you actually have.)

---

## Platform support

| OS | Status | Notes |
|---|---|---|
| Ubuntu 22.04+ | Fully tested | Recommended |
| Ubuntu 20.04 | Works | Manual Node 20 install required |
| Debian 12 | Works | Same as Ubuntu |
| Fedora 39+ | Theoretical | Script has a dnf path, not live tested |
| Raspberry Pi OS | Theoretical | armhf/arm64 should work; cloudflared arm64 build is auto-installed |
| macOS | Dev only | Use `PocketClot Server.command` (Tkinter GUI) in the repo root |
| Windows | Not supported | Use WSL2 with Ubuntu |

---

## FAQ

**Do I need a domain?**
No — the default path (Tailscale Funnel) works without a domain. Your own
domain is only useful if you already have one at Cloudflare and want to put,
for example, Cloudflare Access as an additional login layer in front of the
app.

**What does all this cost?**
- Tailscale Funnel: 0 on the Free plan (50 GB of public bandwidth per month —
  easily 100x more than personal chat usage).
- Cloudflare Named Tunnel: 0 (if you have a domain at Cloudflare).
- Claude subscription: ongoing cost depending on the plan (Pro / Max / API).
- Cloud TTS (optional): see `data/INITIAL_PASSWORD.txt` and the billing
  widget in the TTS settings. The free tier is enough for personal use.

**How many devices can connect?**
Any number. Multi-user auth is built in — create a separate user per
person/device (App → Settings → Admin → User management).

**What about push notifications?**
They work — the app starts a foreground service during streaming and posts
a "reply ready" notification when the app was in the background.

**Can I run multiple PocketClot servers in parallel?**
Yes. Each has its own URL, and you create one app profile per server. For
example, one at home (Cloudflare domain) and one for travel (Tailscale).
