#!/bin/bash
# Publish Hassan AI on hassanai.xyz (VPS)
# Usage: cd ~/hassanaiagent && bash deploy/vps-setup.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/root/hassanaiagent}"
DOMAIN="hassanai.xyz"
EMAIL="${CERTBOT_EMAIL:-hassanchannel637@gmail.com}"

echo "==> Update app from GitHub"
cd "$APP_DIR"
git pull origin main

echo "==> Python deps"
if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
# shellcheck disable=SC1091
source "$APP_DIR/venv/bin/activate"
pip install -U pip
pip install -r "$APP_DIR/requirements.txt"

echo "==> Stop manual run_web if port 8080 busy (systemd will take over)"
fuser -k 8080/tcp 2>/dev/null || true

echo "==> Install Nginx + Certbot (if missing)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y nginx certbot python3-certbot-nginx

echo "==> Nginx site config"
cp "$APP_DIR/deploy/nginx/hassanai.xyz.conf" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "==> Systemd service (app on 127.0.0.1:8080)"
cp "$APP_DIR/deploy/systemd/hassan-ai.service" /etc/systemd/system/hassan-ai.service
systemctl daemon-reload
systemctl enable hassan-ai
systemctl restart hassan-ai

echo "==> SSL (Let's Encrypt) — DNS must point $DOMAIN to this server"
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
  --non-interactive --agree-tos -m "$EMAIL" --redirect || {
  echo ""
  echo "Certbot failed. Check DNS first:"
  echo "  dig +short hassanai.xyz"
  echo "  dig +short www.hassanai.xyz"
  echo "Both should show your VPS IP. Then run:"
  echo "  certbot --nginx -d $DOMAIN -d www.$DOMAIN"
}

echo ""
echo "==> Done"
echo "Site:  https://$DOMAIN"
echo "Admin: https://$DOMAIN/admin"
systemctl status hassan-ai --no-pager || true
