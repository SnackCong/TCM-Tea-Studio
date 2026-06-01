#!/usr/bin/env bash
set -euo pipefail

# Run manually on the VPS during a maintenance window only.
# This recreates mynginx with persistent host-mounted config.
# It does not delete /root/mywebsite or TCM Tea Studio data.

BACKUP_DIR=/root/tcm-tea-studio-backups/$(date +%Y%m%d-%H%M%S)-before-mynginx-persist
mkdir -p "$BACKUP_DIR"
docker inspect mynginx > "$BACKUP_DIR/mynginx-inspect.json"
docker exec mynginx nginx -T > "$BACKUP_DIR/mynginx-nginx-T.txt"
cp -a /root/mywebsite "$BACKUP_DIR/mywebsite"

docker stop mynginx
docker rename mynginx mynginx-before-persist-$(date +%Y%m%d%H%M%S)

docker run -d \
  --name mynginx \
  --restart unless-stopped \
  -p 80:80 \
  -v /opt/tcm-tea-studio/nginx-persistent/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v /opt/tcm-tea-studio/nginx-persistent/conf.d:/etc/nginx/conf.d:ro \
  -v /root/mywebsite:/usr/share/nginx/html:ro \
  nginx

docker exec mynginx nginx -t
curl -I http://127.0.0.1
curl -I -H 'Host: congnet.xyz' http://127.0.0.1
