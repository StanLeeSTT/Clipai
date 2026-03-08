#!/bin/bash
# ClipAI Start Script — works on Termux, Linux, Mac, WSL
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

cd "$(dirname "$0")"

echo -e "${CYAN}${BOLD}  ▶ Starting ClipAI...${NC}\n"

# Activate venv if present (created by install.sh on Linux/Mac/WSL)
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
  PYTHON=".venv/bin/python"
elif [ -f ".venv/Scripts/activate" ]; then
  source .venv/Scripts/activate
  PYTHON=".venv/Scripts/python"
elif command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo -e "${RED}✗ Python not found. Run install.sh first.${NC}"; exit 1
fi

# Self-heal: install flask-cors if missing (catches the exact error you hit)
if ! $PYTHON -c "import flask_cors" 2>/dev/null; then
  echo -e "${YELLOW}⚠ flask-cors missing, installing now...${NC}"
  $PYTHON -m pip install flask-cors --quiet 2>/dev/null || \
  $PYTHON -m pip install flask-cors --break-system-packages --quiet 2>/dev/null || \
  { echo -e "${RED}✗ Could not install flask-cors${NC}"; exit 1; }
  echo -e "${GREEN}✓ flask-cors installed${NC}\n"
fi

# Self-heal: check all critical imports before starting
MISSING=""
for pkg in flask yt_dlp; do
  $PYTHON -c "import $pkg" 2>/dev/null || MISSING="$MISSING $pkg"
done
if [ -n "$MISSING" ]; then
  echo -e "${YELLOW}⚠ Missing packages:$MISSING — attempting install...${NC}"
  for pkg in $MISSING; do
    pip_name=$(echo "$pkg" | sed 's/_/-/g')
    $PYTHON -m pip install "$pip_name" --quiet 2>/dev/null || \
    $PYTHON -m pip install "$pip_name" --break-system-packages --quiet 2>/dev/null || true
  done
fi

if [ ! -f "app.py" ]; then
  echo -e "${RED}✗ app.py not found. Are you in the clipai directory?${NC}"; exit 1
fi

# Get local IP
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IP" ] && IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)

echo -e "${GREEN}✓ Server starting...${NC}\n"
echo -e "  📱 Local:    ${CYAN}http://localhost:5000${NC}"
[ -n "$IP" ] && echo -e "  🌐 Network:  ${CYAN}http://$IP:5000${NC}"
echo -e "\n  Press ${BOLD}Ctrl+C${NC} to stop\n"

$PYTHON app.py
