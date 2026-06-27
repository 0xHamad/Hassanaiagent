#!/bin/bash
# Run on VPS as root AFTER hassanag.is-a.dev DNS points to this server.
# Usage: cd ~/hassanaiagent && bash deploy/vps-setup.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/root/hassanaiagent}"
DOMAIN="hassanag.is-a.dev"

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

echo "==> Install Nginx + Certbot (if missing)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y nginx certbot python3-certbot-nginx

echo "==> Nginx site config"
cp "$APP_DIR/deploy/nginx/hassanag.is-a.dev.conf" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "==> Systemd service"
cp "$APP_DIR/deploy/systemd/hassan-ai.service" /etc/systemd/system/hassan-ai.service
systemctl daemon-reload
systemctl enable hassan-ai
systemctl restart hassan-ai

echo "==> SSL (Let's Encrypt) — needs DNS already live for $DOMAIN"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m hassanchannel637@gmail.com --redirect || {
  echo "Certbot failed. Wait until hassanag.is-a.dev resolves to this VPS IP, then run:"
  echo "  certbot --nginx -d $DOMAIN"
}

echo "==> Done"
echo "App:  https://$DOMAIN"
echo "Admin: https://$DOMAIN/admin"
systemctl status hassan-ai --no-pager || true
