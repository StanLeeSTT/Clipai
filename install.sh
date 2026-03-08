#!/bin/bash
# ============================================================
#  ClipAI Installer
#  Supports: Android/Termux · Linux · macOS · Windows/WSL
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PYTHON=""
ENV=""
VENV_DIR=".venv"

banner() {
  echo -e "${CYAN}"
  echo "  ██████╗██╗     ██╗██████╗  █████╗ ██╗"
  echo " ██╔════╝██║     ██║██╔══██╗██╔══██╗██║"
  echo " ██║     ██║     ██║██████╔╝███████║██║"
  echo " ██║     ██║     ██║██╔═══╝ ██╔══██║██║"
  echo " ╚██████╗███████╗██║██║     ██║  ██║██║"
  echo "  ╚═════╝╚══════╝╚═╝╚═╝     ╚═╝  ╚═╝╚═╝"
  echo -e "${NC}"
  echo -e "${BOLD}  AI Video Clipping Engine — Local & Private${NC}"
  echo -e "  ─────────────────────────────────────────\n"
}

check_cmd() { command -v "$1" &>/dev/null; }

# ── Detect OS / environment ──────────────────────────────
detect_env() {
  if [ -d "/data/data/com.termux" ] || [ "$PREFIX" = "/data/data/com.termux/files/usr" ]; then
    ENV="termux"
    echo -e "${GREEN}✓ Detected: Termux (Android $(uname -m))${NC}"
  elif grep -qi microsoft /proc/version 2>/dev/null; then
    ENV="wsl"
    echo -e "${GREEN}✓ Detected: Windows WSL ($(uname -m))${NC}"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ENV="linux"
    echo -e "${GREEN}✓ Detected: Linux ($(uname -m))${NC}"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    ENV="mac"
    echo -e "${GREEN}✓ Detected: macOS ($(uname -m))${NC}"
  else
    ENV="unknown"
    echo -e "${YELLOW}⚠ Unknown environment, attempting generic install${NC}"
  fi
}

# ── System packages ──────────────────────────────────────
install_system_deps() {
  case $ENV in
    termux)
      echo -e "\n${BLUE}📦 Installing Termux packages...${NC}"
      pkg update -y 2>/dev/null || true
      for p in python python-pip ffmpeg git curl nodejs; do
        if pkg list-installed 2>/dev/null | grep -q "^$p/"; then
          echo -e "  ${GREEN}✓ $p${NC}"
        else
          echo -ne "  Installing $p... "
          pkg install -y "$p" 2>/dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠ skipped${NC}"
        fi
      done
      ;;
    linux|wsl)
      echo -e "\n${BLUE}📦 Checking Linux system packages...${NC}"
      if check_cmd apt-get; then
        echo -ne "  Updating package list... "
        sudo apt-get update -qq 2>/dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠${NC}"
        for p in python3 python3-pip python3-venv python3-full ffmpeg git curl nodejs; do
          echo -ne "  $p... "
          sudo apt-get install -y "$p" -qq 2>/dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠ skipped${NC}"
        done
      elif check_cmd dnf; then
        for p in python3 python3-pip ffmpeg git curl nodejs; do
          sudo dnf install -y "$p" 2>/dev/null || true
        done
      elif check_cmd pacman; then
        for p in python python-pip ffmpeg git curl nodejs; do
          sudo pacman -S --noconfirm "$p" 2>/dev/null || true
        done
      else
        echo -e "${YELLOW}⚠ Unknown package manager. Please install python3, ffmpeg, git manually.${NC}"
      fi
      ;;
    mac)
      echo -e "\n${BLUE}📦 Checking macOS packages...${NC}"
      if ! check_cmd brew; then
        echo -e "  ${YELLOW}Homebrew not found. Installing...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" 2>/dev/null || true
      fi
      for p in python3 ffmpeg git node; do
        echo -ne "  $p... "
        brew install "$p" 2>/dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${YELLOW}⚠ skipped${NC}"
      done
      ;;
  esac
}

# ── pip Android CPU patch (Termux only) ──────────────────
fix_pip_android_arch() {
  [ "$ENV" != "termux" ] && return
  echo -e "\n${BLUE}🔧 Applying Android CPU patch...${NC}"
  TAGS_FILES=$(find /data/data/com.termux/files/usr/lib/ -name "tags.py" -path "*/pip/*" 2>/dev/null)
  for TAGS_FILE in $TAGS_FILES; do
    grep -q "armv8l" "$TAGS_FILE" 2>/dev/null && { echo -e "  ${GREEN}✓ Already patched${NC}"; continue; }
    cp "$TAGS_FILE" "${TAGS_FILE}.bak" 2>/dev/null || true
    sed -i 's/"armv7l": "armeabi_v7a",/"armv7l": "armeabi_v7a",\n        "armv8l": "aarch64",\n        "armv8": "aarch64",/' "$TAGS_FILE" 2>/dev/null && \
      echo -e "  ${GREEN}✓ Patched${NC}" || echo -e "  ${YELLOW}⚠ Patch skipped${NC}"
  done
}

# ── Python setup ─────────────────────────────────────────
setup_python() {
  echo -e "\n${BLUE}🐍 Setting up Python...${NC}"
  if check_cmd python3; then
    PYTHON=python3
  elif check_cmd python; then
    PYTHON=python
  else
    echo -e "${RED}✗ Python not found! Please install Python 3.8+${NC}"; exit 1
  fi
  PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  echo -e "  ${GREEN}✓ Python $PYVER${NC}"
  $PYTHON -m pip install --upgrade pip --quiet 2>/dev/null || true
}

# ── Smart pip install: tries multiple methods ────────────
# On Linux/Mac: uses a virtualenv to avoid system Python restrictions
# On Termux: installs directly (no system protection)
setup_venv() {
  if [ "$ENV" = "termux" ]; then
    return  # Termux doesn't need/want venv
  fi

  echo -e "\n${BLUE}🔒 Setting up virtual environment...${NC}"
  if [ -d "$VENV_DIR" ]; then
    echo -e "  ${GREEN}✓ Existing venv found${NC}"
  else
    echo -ne "  Creating .venv... "
    $PYTHON -m venv "$VENV_DIR" 2>/dev/null || $PYTHON -m venv "$VENV_DIR" --without-pip 2>/dev/null
    if [ -d "$VENV_DIR" ]; then
      echo -e "${GREEN}✓${NC}"
    else
      echo -e "${YELLOW}⚠ venv creation failed, will install globally${NC}"
      return
    fi
  fi

  # Activate the venv
  if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    PYTHON="$VENV_DIR/bin/python"
    echo -e "  ${GREEN}✓ Venv activated — packages install here, not system-wide${NC}"
  elif [ -f "$VENV_DIR/Scripts/activate" ]; then  # Windows path
    source "$VENV_DIR/Scripts/activate"
    PYTHON="$VENV_DIR/Scripts/python"
    echo -e "  ${GREEN}✓ Venv activated (Windows path)${NC}"
  fi

  # Upgrade pip inside venv
  $PYTHON -m pip install --upgrade pip --quiet 2>/dev/null || true
}

pip_install() {
  local pkg="$1"
  local label="${2:-$1}"
  local optional="${3:-required}"

  echo -ne "    $label... "

  # Already installed check
  local import_name
  import_name=$(echo "$pkg" | sed 's/-/_/g' | tr '[:upper:]' '[:lower:]' | sed 's/python_//' | sed 's/openai_whisper/whisper/' | sed 's/pillow/PIL/' | sed 's/gtts/gtts/')
  $PYTHON -c "import $import_name" 2>/dev/null && { echo -e "${GREEN}✓ already installed${NC}"; return 0; }

  # Try installing — order of methods depends on environment
  if [ "$ENV" = "termux" ]; then
    # Termux: direct pip, no venv needed
    $PYTHON -m pip install "$pkg" --quiet 2>/dev/null && { echo -e "${GREEN}✓${NC}"; return 0; }
    pip install "$pkg" --quiet 2>/dev/null && { echo -e "${GREEN}✓${NC}"; return 0; }
  else
    # Linux/Mac/WSL: use venv pip (already activated above)
    $PYTHON -m pip install "$pkg" --quiet 2>/dev/null && { echo -e "${GREEN}✓${NC}"; return 0; }
    # Fallback: --break-system-packages for Ubuntu 23+ without venv
    $PYTHON -m pip install "$pkg" --break-system-packages --quiet 2>/dev/null && { echo -e "${GREEN}✓${NC}"; return 0; }
    pip3 install "$pkg" --break-system-packages --quiet 2>/dev/null && { echo -e "${GREEN}✓${NC}"; return 0; }
  fi

  if [ "$optional" = "optional" ]; then
    echo -e "${YELLOW}⚠ skipped (optional)${NC}"
  else
    echo -e "${RED}✗ FAILED${NC}"
  fi
  return 1
}

install_python_deps() {
  echo -e "\n${BLUE}📚 Installing Python packages...${NC}"

  echo -e "\n  ${CYAN}── Core (required) ──${NC}"
  pip_install "flask"           "Flask"
  pip_install "flask-cors"      "Flask-CORS"
  pip_install "yt-dlp"          "yt-dlp"
  pip_install "requests"        "requests"
  pip_install "tqdm"            "tqdm"
  pip_install "colorama"        "colorama"
  pip_install "python-dotenv"   "python-dotenv"

  echo -e "\n  ${CYAN}── Media (recommended) ──${NC}"
  pip_install "moviepy"  "moviepy"  "optional"
  pip_install "Pillow"   "Pillow"   "optional"
  pip_install "numpy"    "numpy"    "optional"

  echo -e "\n  ${CYAN}── AI (optional — enables Full AI mode) ──${NC}"
  echo -e "  ${YELLOW}These are large downloads. ClipAI works without them.${NC}"
  pip_install "gTTS"             "gTTS (voice)"        "optional"
  pip_install "openai-whisper"   "Whisper (AI clips)"  "optional"
  pip_install "transformers"     "Transformers"        "optional"
}

# ── Directories ──────────────────────────────────────────
setup_dirs() {
  echo -e "\n${BLUE}📁 Creating directories...${NC}"
  mkdir -p uploads clips logs models/weights
  echo -e "  ${GREEN}✓ uploads/ clips/ logs/ models/weights/${NC}"
}

# ── Config ───────────────────────────────────────────────
create_config() {
  echo -e "\n${BLUE}⚙️  Config...${NC}"
  if [ ! -f "config.py" ]; then
    cat > config.py << 'CONFIGEOF'
import os
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
DEBUG = False
UPLOAD_FOLDER = "uploads"
CLIPS_FOLDER = "clips"
MAX_CONTENT_LENGTH = 500 * 1024 * 1024
DEFAULT_CLIP_DURATIONS = [15, 30, 60]
MAX_CLIPS_PER_VIDEO = 5
MIN_CLIP_SCORE = 0.35
OUTPUT_FPS = 30
WHISPER_MODEL = "base"
USE_GPU = False
FALLBACK_MODE = True
ENABLE_VOICE_NARRATION = True
VOICE_LANGUAGE = "en"
ENABLE_SUBTITLES = True
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v', '3gp'}
CONFIGEOF
    echo -e "  ${GREEN}✓ config.py created${NC}"
  else
    echo -e "  ${GREEN}✓ config.py already exists${NC}"
  fi
}

# ── Write start.sh with venv awareness ──────────────────
write_start_sh() {
  echo -e "\n${BLUE}✍️  Writing start.sh...${NC}"
  cat > start.sh << 'STARTEOF'
#!/bin/bash
# ClipAI Start Script — auto-detects venv
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

cd "$(dirname "$0")"

echo -e "${CYAN}${BOLD}  ▶ Starting ClipAI...${NC}\n"

# Activate venv if it exists (Linux/Mac/WSL)
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

# Verify flask_cors is available before starting
if ! $PYTHON -c "import flask_cors" 2>/dev/null; then
  echo -e "${YELLOW}⚠ flask-cors missing, installing now...${NC}"
  $PYTHON -m pip install flask-cors --quiet 2>/dev/null || \
  $PYTHON -m pip install flask-cors --break-system-packages --quiet 2>/dev/null || \
  { echo -e "${RED}✗ Could not install flask-cors. Run: pip install flask-cors${NC}"; exit 1; }
  echo -e "${GREEN}✓ flask-cors installed${NC}\n"
fi

if [ ! -f "app.py" ]; then
  echo -e "${RED}✗ app.py not found. Are you in the clipai directory?${NC}"; exit 1
fi

# Get local IP
if command -v hostname &>/dev/null; then
  IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "$IP" ]; then
  IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
fi

echo -e "${GREEN}✓ Server starting...${NC}\n"
echo -e "  📱 Local:    ${CYAN}http://localhost:5000${NC}"
[ -n "$IP" ] && echo -e "  🌐 Network:  ${CYAN}http://$IP:5000${NC}"
echo -e "\n  Press ${BOLD}Ctrl+C${NC} to stop\n"

$PYTHON app.py
STARTEOF
  chmod +x start.sh
  echo -e "  ${GREEN}✓ start.sh updated${NC}"
}

# ── Write start.bat for Windows (no WSL) ─────────────────
write_start_bat() {
  cat > start.bat << 'BATEOF'
@echo off
cd /d "%~dp0"
echo.
echo   ClipAI Starting...
echo.

REM Try venv first
if exist ".venv\Scripts\python.exe" (
  set PYTHON=.venv\Scripts\python.exe
) else if exist ".venv\Scripts\python3.exe" (
  set PYTHON=.venv\Scripts\python3.exe
) else (
  set PYTHON=python
)

REM Check flask_cors
%PYTHON% -c "import flask_cors" 2>nul
if errorlevel 1 (
  echo Installing flask-cors...
  %PYTHON% -m pip install flask-cors
)

echo   Open in browser: http://localhost:5000
echo   Press Ctrl+C to stop
echo.
%PYTHON% app.py
pause
BATEOF
  echo -e "  ${GREEN}✓ start.bat written (for Windows)${NC}"
}

# ── Install bat for Windows too ──────────────────────────
write_install_bat() {
  cat > install.bat << 'IBATEOF'
@echo off
cd /d "%~dp0"
echo ClipAI Windows Installer
echo.

python --version 2>nul || (echo Python not found. Install from https://python.org && pause && exit /b)

echo Creating virtual environment...
python -m venv .venv

echo Activating...
call .venv\Scripts\activate.bat

echo Installing packages...
pip install flask flask-cors yt-dlp requests tqdm colorama python-dotenv moviepy Pillow numpy
echo.
echo Optional AI packages ^(large download^):
set /p AI=Install Whisper AI? (y/n): 
if /i "%AI%"=="y" pip install openai-whisper gTTS transformers

echo Creating directories...
if not exist uploads mkdir uploads
if not exist clips mkdir clips
if not exist logs mkdir logs

echo.
echo Done! Run start.bat to launch ClipAI.
pause
IBATEOF
  echo -e "  ${GREEN}✓ install.bat written (for Windows)${NC}"
}

# ── FFmpeg check ─────────────────────────────────────────
check_ffmpeg() {
  echo -e "\n${BLUE}🎬 FFmpeg...${NC}"
  if check_cmd ffmpeg; then
    FFVER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    echo -e "  ${GREEN}✓ FFmpeg $FFVER${NC}"
  else
    echo -e "  ${RED}✗ FFmpeg not found!${NC}"
    case $ENV in
      termux) echo -e "  ${YELLOW}Fix: pkg install ffmpeg${NC}" ;;
      linux|wsl) echo -e "  ${YELLOW}Fix: sudo apt install ffmpeg${NC}" ;;
      mac)    echo -e "  ${YELLOW}Fix: brew install ffmpeg${NC}" ;;
      *)      echo -e "  ${YELLOW}Download from: https://ffmpeg.org/download.html${NC}" ;;
    esac
  fi
}

# ── Verify ───────────────────────────────────────────────
verify() {
  echo -e "\n${BLUE}🔍 Verifying...${NC}"
  $PYTHON -c "import flask" 2>/dev/null       && echo -e "  ${GREEN}✓ Flask${NC}"        || echo -e "  ${RED}✗ Flask MISSING${NC}"
  $PYTHON -c "import flask_cors" 2>/dev/null  && echo -e "  ${GREEN}✓ Flask-CORS${NC}"   || echo -e "  ${RED}✗ Flask-CORS MISSING${NC}"
  $PYTHON -c "import yt_dlp" 2>/dev/null      && echo -e "  ${GREEN}✓ yt-dlp${NC}"       || echo -e "  ${YELLOW}⚠ yt-dlp missing${NC}"
  check_cmd ffmpeg                             && echo -e "  ${GREEN}✓ FFmpeg${NC}"        || echo -e "  ${RED}✗ FFmpeg MISSING${NC}"
  $PYTHON -c "import whisper" 2>/dev/null     && echo -e "  ${GREEN}✓ Whisper (AI mode)${NC}" || echo -e "  ${YELLOW}⚠ Whisper missing — basic mode${NC}"
}

# ── Final message ────────────────────────────────────────
final_msg() {
  IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
  echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${GREEN}  ✅ ClipAI Ready!${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
  if [ "$ENV" = "termux" ] || [ "$ENV" = "linux" ] || [ "$ENV" = "mac" ] || [ "$ENV" = "wsl" ]; then
    echo -e "  ${BOLD}Start:${NC}  ${CYAN}bash start.sh${NC}"
  fi
  echo -e "  ${BOLD}Windows:${NC} ${CYAN}double-click start.bat${NC}"
  echo -e ""
  echo -e "  ${BOLD}Open browser at:${NC}"
  echo -e "  ${CYAN}http://localhost:5000${NC}"
  [ -n "$IP" ] && echo -e "  ${CYAN}http://$IP:5000${NC}  ← other devices on same WiFi\n"
}

# ══════════ MAIN ══════════
banner
detect_env
install_system_deps
fix_pip_android_arch
setup_python
setup_venv
install_python_deps
setup_dirs
check_ffmpeg
create_config
write_start_sh
write_start_bat
write_install_bat
verify
final_msg
