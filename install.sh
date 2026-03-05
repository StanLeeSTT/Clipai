#!/bin/bash

# ============================================================
#  ClipAI Installer — Works on Termux (Android) & Linux
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

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
  echo -e "  ─────────────────────────────────────────"
  echo ""
}

detect_env() {
  if [ -d "/data/data/com.termux" ] || [ "$PREFIX" = "/data/data/com.termux/files/usr" ]; then
    ENV="termux"
    echo -e "${GREEN}✓ Detected: Termux (Android)${NC}"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ENV="linux"
    echo -e "${GREEN}✓ Detected: Linux${NC}"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    ENV="mac"
    echo -e "${GREEN}✓ Detected: macOS${NC}"
  else
    ENV="unknown"
    echo -e "${YELLOW}⚠ Unknown environment, attempting generic install${NC}"
  fi
}

check_cmd() {
  command -v "$1" &>/dev/null
}

install_system_deps_termux() {
  echo -e "\n${BLUE}📦 Installing system packages via pkg...${NC}"
  pkg update -y 2>/dev/null || true
  
  PKGS=("python" "ffmpeg" "git" "curl" "clang" "libffi" "openssl" "libjpeg-turbo" "libpng" "rust")
  for pkg in "${PKGS[@]}"; do
    if ! check_cmd "$pkg" 2>/dev/null; then
      echo -e "  Installing ${pkg}..."
      pkg install -y "$pkg" 2>/dev/null || echo -e "  ${YELLOW}⚠ Could not install $pkg, skipping${NC}"
    else
      echo -e "  ${GREEN}✓ $pkg already installed${NC}"
    fi
  done
}

install_system_deps_linux() {
  echo -e "\n${BLUE}📦 Checking system packages...${NC}"
  
  if check_cmd apt-get; then
    PM="apt-get"
    INSTALL_CMD="sudo apt-get install -y"
    PKGS=("python3" "python3-pip" "ffmpeg" "git" "curl" "build-essential" "libffi-dev" "libssl-dev")
  elif check_cmd dnf; then
    PM="dnf"
    INSTALL_CMD="sudo dnf install -y"
    PKGS=("python3" "python3-pip" "ffmpeg" "git" "curl" "gcc" "libffi-devel" "openssl-devel")
  elif check_cmd pacman; then
    PM="pacman"
    INSTALL_CMD="sudo pacman -S --noconfirm"
    PKGS=("python" "python-pip" "ffmpeg" "git" "curl" "base-devel" "libffi" "openssl")
  else
    echo -e "${YELLOW}⚠ Package manager not found. Please install python3, ffmpeg, git manually.${NC}"
    return
  fi

  for pkg in "${PKGS[@]}"; do
    echo -e "  Checking $pkg..."
    $INSTALL_CMD "$pkg" 2>/dev/null || echo -e "  ${YELLOW}⚠ Could not install $pkg${NC}"
  done
}

setup_python_env() {
  echo -e "\n${BLUE}🐍 Setting up Python environment...${NC}"
  
  # Determine python command
  if check_cmd python3; then
    PYTHON=python3
    PIP=pip3
  elif check_cmd python; then
    PYTHON=python
    PIP=pip
  else
    echo -e "${RED}✗ Python not found! Please install Python 3.8+${NC}"
    exit 1
  fi

  PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  echo -e "  ${GREEN}✓ Python $PYVER found${NC}"

  # Upgrade pip
  $PYTHON -m pip install --upgrade pip 2>/dev/null || true
}

install_python_deps() {
  echo -e "\n${BLUE}📚 Installing Python dependencies...${NC}"
  echo -e "  This may take a few minutes on first install...\n"

  # Core packages (lightweight, always install)
  CORE_PKGS=(
    "flask>=2.3.0"
    "flask-cors"
    "yt-dlp"
    "requests"
    "tqdm"
    "colorama"
    "python-dotenv"
  )

  # Media packages
  MEDIA_PKGS=(
    "moviepy"
    "Pillow"
    "numpy"
  )

  # AI packages (heavier)
  AI_PKGS=(
    "openai-whisper"
    "transformers"
    "torch"
    "gTTS"
    "pyttsx3"
  )

  echo -e "  ${CYAN}Installing core packages...${NC}"
  for pkg in "${CORE_PKGS[@]}"; do
    name=$(echo $pkg | cut -d'>' -f1 | cut -d'=' -f1)
    if $PYTHON -c "import $(echo $name | tr '-' '_' | tr '[:upper:]' '[:lower:]')" 2>/dev/null; then
      echo -e "    ${GREEN}✓ $name already installed${NC}"
    else
      echo -e "    Installing $pkg..."
      $PIP install "$pkg" --quiet 2>/dev/null || echo -e "    ${YELLOW}⚠ Failed: $pkg${NC}"
    fi
  done

  echo -e "\n  ${CYAN}Installing media packages...${NC}"
  for pkg in "${MEDIA_PKGS[@]}"; do
    name=$(echo $pkg | cut -d'>' -f1 | cut -d'=' -f1)
    echo -e "    Installing $pkg..."
    $PIP install "$pkg" --quiet 2>/dev/null || echo -e "    ${YELLOW}⚠ Failed: $pkg (may need manual install)${NC}"
  done

  echo -e "\n  ${CYAN}Installing AI packages (this takes longer)...${NC}"
  echo -e "  ${YELLOW}Note: torch installs a CPU-only version for mobile compatibility${NC}"
  
  # torch CPU only for Termux/mobile
  if [ "$ENV" = "termux" ]; then
    $PIP install torch --index-url https://download.pytorch.org/whl/cpu --quiet 2>/dev/null || \
    $PIP install torch --quiet 2>/dev/null || \
    echo -e "    ${YELLOW}⚠ torch install failed — AI features will use fallback mode${NC}"
  else
    $PIP install torch --quiet 2>/dev/null || echo -e "    ${YELLOW}⚠ torch install failed${NC}"
  fi

  for pkg in "${AI_PKGS[@]}"; do
    name=$(echo $pkg | cut -d'>' -f1)
    if [ "$name" != "torch" ]; then
      echo -e "    Installing $pkg..."
      $PIP install "$pkg" --quiet 2>/dev/null || echo -e "    ${YELLOW}⚠ Failed: $pkg${NC}"
    fi
  done
}

setup_directories() {
  echo -e "\n${BLUE}📁 Setting up directories...${NC}"
  mkdir -p uploads clips logs models/weights
  echo -e "  ${GREEN}✓ Created: uploads/, clips/, logs/, models/weights/${NC}"
}

create_config() {
  echo -e "\n${BLUE}⚙️  Creating config file...${NC}"
  if [ ! -f "config.py" ]; then
    cat > config.py << 'CONFIGEOF'
# ClipAI Configuration
import os

# Server
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False

# Paths
UPLOAD_FOLDER = "uploads"
CLIPS_FOLDER = "clips"
LOGS_FOLDER = "logs"
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

# Clip Settings
DEFAULT_CLIP_DURATIONS = [15, 30, 60]   # seconds
MAX_CLIPS_PER_VIDEO = 5
MIN_CLIP_SCORE = 0.4                     # 0-1 virality threshold
OUTPUT_RESOLUTION = (1080, 1920)         # vertical/portrait
OUTPUT_FPS = 30

# AI Settings
WHISPER_MODEL = "base"                   # tiny/base/small/medium
USE_GPU = False                          # set True if GPU available
FALLBACK_MODE = True                     # use simple analysis if AI fails

# Voice Settings
ENABLE_VOICE_NARRATION = True
VOICE_LANGUAGE = "en"

# Subtitles
ENABLE_SUBTITLES = True
SUBTITLE_FONT_SIZE = 48
SUBTITLE_COLOR = "white"
SUBTITLE_BG_COLOR = "black@0.5"

# Allowed upload types
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'm4v', '3gp'}
CONFIGEOF
    echo -e "  ${GREEN}✓ config.py created${NC}"
  else
    echo -e "  ${GREEN}✓ config.py already exists${NC}"
  fi
}

check_ffmpeg() {
  echo -e "\n${BLUE}🎬 Checking FFmpeg...${NC}"
  if check_cmd ffmpeg; then
    FFVER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    echo -e "  ${GREEN}✓ FFmpeg $FFVER found${NC}"
  else
    echo -e "  ${RED}✗ FFmpeg not found!${NC}"
    echo -e "  ${YELLOW}On Termux: pkg install ffmpeg${NC}"
    echo -e "  ${YELLOW}On Ubuntu: sudo apt install ffmpeg${NC}"
    echo -e "  ${YELLOW}Video processing will be limited without FFmpeg${NC}"
  fi
}

final_message() {
  IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
  
  echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${GREEN}  ✅ ClipAI Installation Complete!${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "${BOLD}  To start ClipAI:${NC}"
  echo -e "  ${CYAN}bash start.sh${NC}"
  echo ""
  echo -e "${BOLD}  Then open in your browser:${NC}"
  echo -e "  ${CYAN}http://localhost:5000${NC}"
  if [ "$IP" != "localhost" ] && [ -n "$IP" ]; then
  echo -e "  ${CYAN}http://$IP:5000${NC}  (from other devices on WiFi)"
  fi
  echo ""
  echo -e "${BOLD}  Manual start:${NC}"
  echo -e "  ${CYAN}python app.py${NC}"
  echo ""
}

# ── MAIN ──────────────────────────────────────────────────
banner
detect_env

case $ENV in
  termux) install_system_deps_termux ;;
  linux)  install_system_deps_linux ;;
  mac)    echo -e "${YELLOW}macOS: Please ensure ffmpeg is installed via: brew install ffmpeg${NC}" ;;
esac

setup_python_env
install_python_deps
setup_directories
check_ffmpeg
create_config
final_message
