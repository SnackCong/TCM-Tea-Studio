# Nginx persistence and SSL notes

Current live topology on the VPS:

- TCP 80: Docker proxy forwards to the `mynginx` container.
- TCP 443: host Nginx terminates HTTPS and proxies to `127.0.0.1:8080`.
- UDP 443: `hysteria-server`.
- TCP 8080: `tcm-tea-studio` Python service.

The running `mynginx` container currently only bind-mounts `/root/mywebsite` to `/usr/share/nginx/html`. Its `/etc/nginx/conf.d` is inside the container, so config changes would be lost if the container were recreated.

Prepared persistent layout on the VPS:

```text
/opt/tcm-tea-studio/nginx-persistent/
  nginx.conf
  mime.types
  conf.d/default.conf
  conf.d/zz-congnet.xyz.conf
  html/index.html
  host-ssl-tcm-tea-studio.conf
  migrate-mynginx-persistent.sh
  README.md
```

Do not run `migrate-mynginx-persistent.sh` during normal operation. It is a maintenance-window script that recreates only the `mynginx` container with host-mounted Nginx config and website files.

Cloudflare Full strict preparation:

1. In Cloudflare, create an Origin Certificate for `congnet.xyz` and `www.congnet.xyz`.
2. Put the certificate at `/etc/nginx/ssl/congnet.xyz.crt`.
3. Put the private key at `/etc/nginx/ssl/congnet.xyz.key`.
4. Restrict permissions:

```bash
chmod 600 /etc/nginx/ssl/congnet.xyz.key
nginx -t
systemctl reload nginx
```

Never commit origin certificate private keys to GitHub.
