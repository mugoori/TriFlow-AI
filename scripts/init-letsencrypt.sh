#!/bin/bash
# ===================================================
# TriFlow AI - Let's Encrypt SSL Certificate Setup
# ===================================================
# Usage: ./scripts/init-letsencrypt.sh your-domain.com your@email.com
# ===================================================

set -e

DOMAIN=$1
EMAIL=$2
STAGING=${3:-0}  # Set to 1 for testing

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: $0 <domain> <email> [staging]"
    echo "  domain: Your domain name (e.g., triflow.ai)"
    echo "  email: Email for Let's Encrypt notifications"
    echo "  staging: Set to 1 for testing (optional)"
    exit 1
fi

# Create required directories
echo "Creating directories..."
mkdir -p ./nginx/ssl
mkdir -p ./nginx/certbot/conf
mkdir -p ./nginx/certbot/www

# Download recommended TLS parameters
if [ ! -f "./nginx/ssl/options-ssl-nginx.conf" ]; then
    echo "Downloading recommended TLS parameters..."
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        > ./nginx/ssl/options-ssl-nginx.conf
fi

if [ ! -f "./nginx/ssl/ssl-dhparams.pem" ]; then
    echo "Downloading DH parameters..."
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        > ./nginx/ssl/ssl-dhparams.pem
fi

# Create dummy certificates for nginx to start
echo "Creating dummy certificate for $DOMAIN..."
mkdir -p "./nginx/certbot/conf/live/$DOMAIN"
openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
    -keyout "./nginx/certbot/conf/live/$DOMAIN/privkey.pem" \
    -out "./nginx/certbot/conf/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=$DOMAIN"

# Copy to nginx ssl directory
cp "./nginx/certbot/conf/live/$DOMAIN/privkey.pem" ./nginx/ssl/
cp "./nginx/certbot/conf/live/$DOMAIN/fullchain.pem" ./nginx/ssl/

echo "Starting nginx..."
docker-compose -f docker-compose.prod.yml --profile with-nginx up -d nginx

echo "Waiting for nginx to start..."
sleep 5

# Delete dummy certificate
echo "Deleting dummy certificate..."
rm -rf "./nginx/certbot/conf/live/$DOMAIN"

# Request real certificate
echo "Requesting Let's Encrypt certificate for $DOMAIN..."
STAGING_ARG=""
if [ "$STAGING" = "1" ]; then
    STAGING_ARG="--staging"
    echo "Using staging environment (testing)..."
fi

docker run --rm \
    -v "$(pwd)/nginx/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/nginx/certbot/www:/var/www/certbot" \
    certbot/certbot certonly --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    $STAGING_ARG

# Copy certificates to nginx
echo "Copying certificates..."
cp "./nginx/certbot/conf/live/$DOMAIN/fullchain.pem" ./nginx/ssl/
cp "./nginx/certbot/conf/live/$DOMAIN/privkey.pem" ./nginx/ssl/

# Reload nginx
echo "Reloading nginx..."
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

echo ""
echo "========================================"
echo "SSL Certificate installed successfully!"
echo "========================================"
echo ""
echo "Certificate files:"
echo "  - ./nginx/ssl/fullchain.pem"
echo "  - ./nginx/ssl/privkey.pem"
echo ""
echo "Auto-renewal: Add this to crontab:"
echo "  0 0 1 * * cd /opt/triflow-ai && ./scripts/renew-certs.sh"
echo ""
