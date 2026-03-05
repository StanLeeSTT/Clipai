#!/bin/bash

# ClipAI Start Script
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

cd "$(dirname "$0")"

echo -e "${CYAN}${BOLD}"
echo "  ▶ Starting ClipAI..."
echo -e "${NC}"

# Check python
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo -e "${YELLOW}Python not found. Run install.sh first.${NC}"
  exit 1
fi

# Check app.py
if [ ! -f "app.py" ]; then
  echo -e "${YELLOW}app.py not found. Are you in the clipai directory?${NC}"
  exit 1
fi

# Get local IP
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo -e "${GREEN}✓ Server starting...${NC}"
echo -e ""
echo -e "  📱 Local:    ${CYAN}http://localhost:5000${NC}"
if [ -n "$IP" ] && [ "$IP" != "localhost" ]; then
echo -e "  🌐 Network:  ${CYAN}http://$IP:5000${NC}"
fi
echo -e ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop"
echo -e ""

$PYTHON app.py
