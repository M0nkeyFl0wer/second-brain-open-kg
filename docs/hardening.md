# Security Hardening Session - 2026-01-28

## Issue Discovered
Tailscale was inserting an IPv6 `ACCEPT all ::/0 ::/0` rule that bypassed UFW, exposing services to the public internet via IPv6.

## What Was Exposed
- SSH (22)
- SMTP (25)
- SMB (445)
- SpiderFoot (5001) - Docker container

## What Was Fixed

### Immediate Fixes
All three machines had the Tailscale hole:

```bash
# Laptop, Pi, Arch - all needed:
sudo ip6tables -D ts-input 2
sudo tailscale set --shields-up=true  # (not on Pi - has Funnel)
```

### Persistent Fixes
Created systemd service on all machines: `/etc/systemd/system/fix-tailscale-hole.service`

```bash
sudo systemctl enable fix-tailscale-hole.service
```

### Monitoring Added (Laptop)

| File | Purpose |
|------|---------|
| `~/.local/bin/security-watchdog.sh` | Runs every 5 min, alerts on issues |
| `~/.local/bin/security-audit.sh` | Full manual audit |
| `~/.local/bin/check-watchdog-alive.sh` | Alerts if watchdog dies |
| `~/.config/systemd/user/security-watchdog.timer` | Systemd timer (redundant with cron) |
| `~/.config/autostart/check-watchdog.desktop` | Login check |

Cron entry: `*/5 * * * * /home/flower/.local/bin/security-watchdog.sh`

## Status of Services

| Service | Status | Recommendation |
|---------|--------|----------------|
| smbd/nmbd | Running (not needed) | `sudo systemctl disable --now smbd nmbd` |
| postfix | Running (not needed) | `sudo systemctl disable --now postfix` |
| rpcbind | Running (not needed) | `sudo systemctl disable --now rpcbind` |
| SSH | Using defaults | Run `sudo ~/.local/bin/harden-ssh.sh` |

## Still TODO

- [ ] Disable unneeded services (smbd, postfix, rpcbind)
- [ ] Harden SSH with `~/.local/bin/harden-ssh.sh`
- [ ] Set up YubiKey SSH (see `yubikey-ssh-setup.md`)
- [ ] Check router IPv6 firewall settings

## Key Learnings

1. **Local port scans are unreliable** - traffic to own public IP routes through loopback
2. **Test from external host** - `ssh monk "nc -6 -zv YOUR_IP PORT"`
3. **Tailscale can bypass UFW** - its rules run BEFORE UFW in ip6tables
4. **Docker bypasses UFW** - use `127.0.0.1:port` not `0.0.0.0:port`
5. **IPv6 is directly routable** - no NAT protection like IPv4

## Commands to Remember

```bash
# Check for Tailscale hole
sudo ip6tables -L ts-input -n --line-numbers

# Run security audit
~/.local/bin/security-audit.sh

# Check watchdog status
systemctl --user status security-watchdog.timer
tail -20 /tmp/security-watchdog.log

# Test port from external
ssh monk "nc -6 -zv YOUR_IPV6 22"
```

## Files Created

```
~/.local/bin/
├── security-watchdog.sh
├── security-audit.sh
├── check-watchdog-alive.sh
├── check-firewall-holes.sh
├── harden-ssh.sh
└── install-tailscale-fix.sh

~/.config/systemd/user/
├── security-watchdog.service
└── security-watchdog.timer

~/.config/autostart/
└── check-watchdog.desktop

~/dotfiles/cron/
└── crontab.backup

~/Projects/
├── yubikey-ssh-setup.md
└── security-hardening-2026-01-28.md
```