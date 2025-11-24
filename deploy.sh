#!/bin/bash
#
# SAME Encoder/Decoder Deployment Script
# Handles installation and systemd service setup
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="same-endec"
SERVICE_USER="${SUDO_USER:-$USER}"
BACKEND_PORT=8000
FRONTEND_PORT=8080
USE_NGINX=true  # Set to false to run without nginx (development mode)

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}SAME Encoder/Decoder Deployment${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check if running on Ubuntu/Debian
check_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
            echo -e "${YELLOW}Warning: This script is designed for Ubuntu/Debian. Your OS: $ID${NC}"
            read -p "Continue anyway? (y/n) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
}

# Install system dependencies
install_dependencies() {
    echo -e "${GREEN}[1/6] Installing system dependencies...${NC}"

    sudo apt-get update

    if [ "$USE_NGINX" = true ]; then
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            git \
            nginx
    else
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            git
    fi

    echo -e "${GREEN}Dependencies installed successfully${NC}"
}

# Set up Python virtual environment
setup_venv() {
    echo -e "${GREEN}[2/6] Setting up Python virtual environment...${NC}"

    cd "$PROJECT_DIR/backend"

    if [ -d "venv" ]; then
        echo "Virtual environment already exists, skipping creation"
    else
        python3 -m venv venv
    fi

    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate

    echo -e "${GREEN}Python environment configured${NC}"
}

# Initialize FIPS code database
init_fips_db() {
    echo -e "${GREEN}[3/6] Initializing FIPS code database...${NC}"

    cd "$PROJECT_DIR/backend"

    # Check if database already exists
    if [ -f "fips_codes.db" ]; then
        echo "FIPS database already exists, skipping initialization"
    else
        # Run initialization script
        source venv/bin/activate
        python3 init_fips_db.py
        deactivate
    fi

    echo -e "${GREEN}FIPS database ready${NC}"
}

# Generate static EOM WAV file
generate_eom() {
    echo -e "${GREEN}[4/6] Generating static EOM WAV file...${NC}"

    cd "$PROJECT_DIR/backend"

    # Check if EOM file already exists
    if [ -f "../frontend/eom.wav" ]; then
        echo "EOM WAV file already exists, skipping generation"
    else
        # Generate EOM file
        source venv/bin/activate
        python3 generate_eom.py
        deactivate
    fi

    echo -e "${GREEN}EOM WAV file ready${NC}"
}

# Create systemd service for backend
create_backend_service() {
    echo -e "${GREEN}[5/6] Creating systemd service for backend...${NC}"

    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}-backend.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=SAME Encoder/Decoder Backend API
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="ALLOWED_ORIGINS=http://localhost:$FRONTEND_PORT"
ExecStart=$PROJECT_DIR/backend/venv/bin/python api.py
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$PROJECT_DIR

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}-backend.service"

    echo -e "${GREEN}Backend service created: ${SERVICE_NAME}-backend.service${NC}"
}

# Create systemd service for frontend (only if not using nginx)
create_frontend_service() {
    if [ "$USE_NGINX" = true ]; then
        echo -e "${YELLOW}Skipping frontend service (using nginx instead)${NC}"
        return
    fi

    echo -e "${GREEN}[6/6] Creating systemd service for frontend...${NC}"

    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}-frontend.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=SAME Encoder/Decoder Frontend Web Server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR/frontend
ExecStart=/usr/bin/python3 -m http.server $FRONTEND_PORT
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}-frontend.service"

    echo -e "${GREEN}Frontend service created: ${SERVICE_NAME}-frontend.service${NC}"
}

# Configure nginx reverse proxy
configure_nginx() {
    if [ "$USE_NGINX" = false ]; then
        return
    fi

    echo -e "${GREEN}[6/6] Configuring nginx reverse proxy...${NC}"

    # Update nginx config with correct path
    NGINX_CONF="/etc/nginx/sites-available/${SERVICE_NAME}"

    sudo tee "$NGINX_CONF" > /dev/null <<EOF
# Nginx configuration for SAME Encoder/Decoder
# Auto-generated by deploy.sh

server {
    listen 80;
    server_name _;  # Replace with your domain name

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Maximum upload size (matches backend 10MB limit)
    client_max_body_size 10M;

    # Logging
    access_log /var/log/nginx/${SERVICE_NAME}-access.log;
    error_log /var/log/nginx/${SERVICE_NAME}-error.log;

    # Frontend - serve static files
    location / {
        root $PROJECT_DIR/frontend;
        index index.html;
        try_files \$uri \$uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)\$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # Don't cache HTML
        location ~* \.html\$ {
            expires -1;
            add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
        }
    }

    # Backend API - reverse proxy to FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_http_version 1.1;

        # Forward client information
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Disable buffering for streaming responses
        proxy_buffering off;
    }

    # API docs endpoints
    location ~ ^/(docs|redoc|openapi.json|health)\$ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_http_version 1.1;

        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

    # Enable site
    sudo ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/${SERVICE_NAME}"

    # Remove default site if it exists
    sudo rm -f /etc/nginx/sites-enabled/default

    # Test nginx configuration
    sudo nginx -t

    # Reload nginx
    sudo systemctl enable nginx
    sudo systemctl reload nginx

    echo -e "${GREEN}Nginx configured and reloaded${NC}"
    echo -e "${YELLOW}Note: Replace 'server_name _;' with your domain in $NGINX_CONF${NC}"
    echo -e "${YELLOW}Then secure with: sudo certbot --nginx -d your-domain.com${NC}"
}

# Start services
start_services() {
    echo -e "${GREEN}Starting services...${NC}"

    sudo systemctl start "${SERVICE_NAME}-backend.service"

    if [ "$USE_NGINX" = false ]; then
        sudo systemctl start "${SERVICE_NAME}-frontend.service"
    fi

    sleep 2

    # Check status
    echo ""
    echo -e "${GREEN}Backend status:${NC}"
    sudo systemctl status "${SERVICE_NAME}-backend.service" --no-pager | head -n 10

    if [ "$USE_NGINX" = false ]; then
        echo ""
        echo -e "${GREEN}Frontend status:${NC}"
        sudo systemctl status "${SERVICE_NAME}-frontend.service" --no-pager | head -n 10
    else
        echo ""
        echo -e "${GREEN}Nginx status:${NC}"
        sudo systemctl status nginx --no-pager | head -n 10
    fi
}

# Display summary
show_summary() {
    echo ""
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""

    if [ "$USE_NGINX" = true ]; then
        echo "Access Points:"
        echo "  - Application:  http://your-server-ip/"
        echo "  - API Docs:     http://your-server-ip/docs"
        echo ""
        echo "Nginx Configuration:"
        echo "  - Config file:  /etc/nginx/sites-available/${SERVICE_NAME}"
        echo "  - Update server_name with your domain"
        echo "  - Secure with:  sudo certbot --nginx -d your-domain.com"
        echo ""
        echo "Service Management:"
        echo "  - View backend logs: sudo journalctl -u ${SERVICE_NAME}-backend -f"
        echo "  - View nginx logs:   sudo tail -f /var/log/nginx/${SERVICE_NAME}-*.log"
        echo "  - Restart backend:   sudo systemctl restart ${SERVICE_NAME}-backend"
        echo "  - Restart nginx:     sudo systemctl restart nginx"
    else
        echo "Services:"
        echo "  - Backend API: http://localhost:$BACKEND_PORT"
        echo "  - Frontend:    http://localhost:$FRONTEND_PORT"
        echo "  - API Docs:    http://localhost:$BACKEND_PORT/docs"
        echo ""
        echo "Service Management:"
        echo "  - View backend logs:  sudo journalctl -u ${SERVICE_NAME}-backend -f"
        echo "  - View frontend logs: sudo journalctl -u ${SERVICE_NAME}-frontend -f"
        echo "  - Restart backend:    sudo systemctl restart ${SERVICE_NAME}-backend"
        echo "  - Restart frontend:   sudo systemctl restart ${SERVICE_NAME}-frontend"
        echo "  - Stop all:           sudo systemctl stop ${SERVICE_NAME}-{backend,frontend}"
        echo "  - Start all:          sudo systemctl start ${SERVICE_NAME}-{backend,frontend}"
    fi

    echo ""
    echo "Project directory: $PROJECT_DIR"
    echo ""
}

# Main deployment flow
main() {
    check_os
    install_dependencies
    setup_venv
    init_fips_db
    generate_eom
    create_backend_service
    configure_nginx
    create_frontend_service
    start_services
    show_summary
}

# Run main function
main
