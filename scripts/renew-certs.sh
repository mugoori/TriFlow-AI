#!/bin/bash
# ===================================================
# TriFlow AI - SSL Certificate Auto-Renewal
# ===================================================
# Add to crontab: 0 0 1 * * cd /opt/triflow-ai && ./scripts/renew-certs.sh
# ===================================================

set -e

cd "$(dirname "$0")/.."

echo "[$(date)] Starting certificate renewal..."

# Renew certificates
docker run --rm \
    -v "$(pwd)/nginx/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/nginx/certbot/www:/var/www/certbot" \
    certbot/certbot renew --quiet

# Check if certificates were renewed
DOMAIN=$(ls ./nginx/certbot/conf/live/ | head -1)

if [ -n "$DOMAIN" ]; then
    # Copy renewed certificates
    cp "./nginx/certbot/conf/live/$DOMAIN/fullchain.pem" ./nginx/ssl/
    cp "./nginx/certbot/conf/live/$DOMAIN/privkey.pem" ./nginx/ssl/

    # Reload nginx
    docker-compose -f docker-compose.prod.yml exec -T nginx nginx -s reload

    echo "[$(date)] Certificate renewal completed for $DOMAIN"
else
    echo "[$(date)] No certificates found to renew"
fi
