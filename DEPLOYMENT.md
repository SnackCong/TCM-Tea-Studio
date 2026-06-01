# TCM Tea Studio Deployment

Last checked: 2026-06-01

## Overview

Production domain:

- `http://congnet.xyz`
- `https://congnet.xyz`

Application repository:

- `/opt/tcm-tea-studio`

Application data:

- `/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3`

Backups:

- `/root/tcm-tea-studio-backups`

## Runtime Topology

```text
Internet / Cloudflare
  ├─ HTTP  80/tcp  -> Docker mynginx -> 172.17.0.1:8080 -> tcm-tea-studio
  └─ HTTPS 443/tcp -> host nginx     -> 127.0.0.1:8080 -> tcm-tea-studio

Hysteria:
  └─ 443/udp -> hysteria-server
```

## Port Ownership

Current listener map:

- `80/tcp`: Docker proxy for `mynginx`
- `443/tcp`: host `nginx`
- `443/udp`: `hysteria-server`
- `8080/tcp`: `python3` running `tcm-tea-studio`

The TCP and UDP listeners on `443` are separate sockets. Host Nginx uses TCP `443`; `hysteria-server` uses UDP `443`.

## Services

Systemd services:

- `nginx`: `enabled`, `active`
- `tcm-tea-studio`: `enabled`, `active`
- `hysteria-server`: `enabled`, `active`
- `hy2`: not active at the time of inspection

Docker containers:

- `mynginx`: running, image `nginx`, publishes `0.0.0.0:80->80/tcp`
- `mynginx-before-persist-20260601052515`: stopped backup container from the persistence migration

## Nginx Layout

Host Nginx handles HTTPS:

- Config: `/etc/nginx/conf.d/tcm-tea-studio-ssl.conf`
- Certificate: `/etc/nginx/ssl/congnet.xyz.crt`
- Private key: `/etc/nginx/ssl/congnet.xyz.key`
- Proxy target: `http://127.0.0.1:8080`

Docker `mynginx` handles HTTP:

- Config source: `/opt/tcm-tea-studio/nginx-persistent/nginx.conf`
- Site configs source: `/opt/tcm-tea-studio/nginx-persistent/conf.d`
- Website files source: `/root/mywebsite`
- Proxy target for `congnet.xyz`: `http://172.17.0.1:8080`

## Docker Mounts

Current `mynginx` bind mounts:

```text
/opt/tcm-tea-studio/nginx-persistent/nginx.conf -> /etc/nginx/nginx.conf:ro
/opt/tcm-tea-studio/nginx-persistent/conf.d    -> /etc/nginx/conf.d:ro
/root/mywebsite                                -> /usr/share/nginx/html:ro
```

Restart policy:

- `mynginx`: `unless-stopped`

This is appropriate for the current deployment. No additional restart policy change is needed.

## Rollback

The previous container was preserved as:

```text
mynginx-before-persist-20260601052515
```

Manual rollback:

```bash
docker stop mynginx
docker rename mynginx mynginx-after-persist-failed-$(date +%Y%m%d%H%M%S)
docker rename mynginx-before-persist-20260601052515 mynginx
docker start mynginx
docker ps
curl -I http://congnet.xyz
```

Do not delete `/root/mywebsite`, `/opt/tcm-tea-studio`, or `/root/tcm-tea-studio-backups`.

## HTTPS Certificate

Current certificate:

- Type: self-signed origin certificate
- Subject: `CN = congnet.xyz`
- Issuer: `CN = congnet.xyz`
- Path: `/etc/nginx/ssl/congnet.xyz.crt`
- Key path: `/etc/nginx/ssl/congnet.xyz.key`
- Valid from: `2026-06-01 04:51:56 GMT`
- Valid until: `2036-05-29 04:51:56 GMT`

The private key currently has restrictive permissions:

```text
-rw------- /etc/nginx/ssl/congnet.xyz.key
```

Cloudflare currently serves HTTPS successfully with this origin setup, which is consistent with Cloudflare SSL/TLS mode being `Full`.

For Cloudflare `Full strict`, replace the current certificate with either:

- Cloudflare Origin Certificate for `congnet.xyz` and `www.congnet.xyz`
- Let's Encrypt certificate trusted by public clients

Recommended Cloudflare Origin Certificate paths:

```text
/etc/nginx/ssl/congnet.xyz.crt
/etc/nginx/ssl/congnet.xyz.key
```

After replacement:

```bash
chmod 600 /etc/nginx/ssl/congnet.xyz.key
nginx -t
systemctl reload nginx
```

Never commit private keys to GitHub.

## Verification Commands

```bash
curl -I http://congnet.xyz
curl -Ik https://congnet.xyz
docker ps
ss -tulpn | grep -E ':80|:443|:8080'
systemctl is-active hysteria-server
systemctl is-active nginx
systemctl is-active tcm-tea-studio
```

Expected high-level results:

- HTTP returns `200 OK`
- HTTPS returns `200`
- `mynginx` is running
- `hysteria-server` is `active`
- `nginx` is `active`
- `tcm-tea-studio` is `active`

## Current Risks

- HTTPS uses a self-signed origin certificate. This works with Cloudflare `Full`, but Cloudflare `Full strict` requires a Cloudflare Origin Certificate or publicly trusted certificate.
- The stopped backup container is useful for rollback, but should not be kept forever without a retention decision.
- Application data is stored in SQLite. Backups should be scheduled before real customer data accumulates.
- The current Python server is intentionally lightweight. For higher traffic or multi-user production, consider moving behind a WSGI/ASGI server and adding structured logging.

## Suggested Next Steps

1. Generate a Cloudflare Origin Certificate and replace the current origin certificate, then switch Cloudflare SSL/TLS to `Full strict`.
2. Add an automated SQLite backup job for `/opt/tcm-tea-studio/data/tcm_tea_studio.sqlite3`.
3. Add a simple deployment script for `git pull && systemctl restart tcm-tea-studio`.
4. Decide a retention date for `mynginx-before-persist-20260601052515`.
