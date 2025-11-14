#!/bin/bash
#
# SAME Encoder/Decoder Deployment Script
# Handles installation, multimon-ng compilation, and systemd service setup
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
    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        cmake \
        libpulse-dev \
        git

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

# Compile multimon-ng
compile_multimon() {
    echo -e "${GREEN}[3/6] Compiling multimon-ng decoder...${NC}"

    cd "$PROJECT_DIR/multimon-ng"

    # Clean previous build if exists
    if [ -d "build" ]; then
        rm -rf build
    fi

    mkdir build
    cd build

    cmake ..
    make

    # Copy binary to bin directory
    mkdir -p "$PROJECT_DIR/bin"
    cp multimon-ng "$PROJECT_DIR/bin/"
    chmod +x "$PROJECT_DIR/bin/multimon-ng"

    echo -e "${GREEN}multimon-ng compiled successfully${NC}"
    echo "Binary location: $PROJECT_DIR/bin/multimon-ng"
}

# Create systemd service for backend
create_backend_service() {
    echo -e "${GREEN}[4/6] Creating systemd service for backend...${NC}"

    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}-backend.service"

    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=SAME Encoder/Decoder Backend API
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$PROJECT_DIR/backend
Environment="PATH=$PROJECT_DIR/backend/venv/bin"
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

# Create systemd service for frontend
create_frontend_service() {
    echo -e "${GREEN}[5/6] Creating systemd service for frontend...${NC}"

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

# Start services
start_services() {
    echo -e "${GREEN}[6/6] Starting services...${NC}"

    sudo systemctl start "${SERVICE_NAME}-backend.service"
    sudo systemctl start "${SERVICE_NAME}-frontend.service"

    sleep 2

    # Check status
    echo ""
    echo -e "${GREEN}Backend status:${NC}"
    sudo systemctl status "${SERVICE_NAME}-backend.service" --no-pager | head -n 10

    echo ""
    echo -e "${GREEN}Frontend status:${NC}"
    sudo systemctl status "${SERVICE_NAME}-frontend.service" --no-pager | head -n 10
}

# Display summary
show_summary() {
    echo ""
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""
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
    echo ""
    echo "Project directory: $PROJECT_DIR"
    echo ""
}

# Main deployment flow
main() {
    check_os
    install_dependencies
    setup_venv
    compile_multimon
    create_backend_service
    create_frontend_service
    start_services
    show_summary
}

# Run main function
main
