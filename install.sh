#!/bin/bash

# ============================================================
#  ClipAI Installer — Works on ALL Android CPUs + Linux/Mac
#  Fixes: pip armv8l KeyError on Python 3.13 + Termux
# ============================================================

# Do NOT use set -e — we handle errors manually for resilience

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

check_cmd() {
  command -v "$1" &>/dev/null
}

detect_env() {
  if [ -d "/data/data/com.termux" ] || [ "$PREFIX" = "/data/data/com.termux/files/usr" ]; then
    ENV="termux"
    echo -e "${GREEN}✓ Detected: Termux (Android)${NC}"
    # Detect exact CPU architecture
    ARCH=$(uname -m 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓ CPU Architecture: $ARCH${NC}"
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ENV="linux"
    ARCH=$(uname -m 2>/dev/null || echo "x86_64")
    echo -e "${GREEN}✓ Detected: Linux ($ARCH)${NC}"
  elif [[ "$OSTYPE" == "darwin"* ]]; then
    ENV="mac"
    ARCH=$(uname -m 2>/dev/null || echo "x86_64")
    echo -e "${GREEN}✓ Detected: macOS ($ARCH)${NC}"
  else
    ENV="unknown"
    ARCH=$(uname -m 2>/dev/null || echo "unknown")
    echo -e "${YELLOW}⚠ Unknown environment ($ARCH), attempting generic install${NC}"
  fi
}

# ── THE KEY FIX: Patch pip's tags.py to support ALL Android CPU variants ──
fix_pip_android_arch() {
  if [ "$ENV" != "termux" ]; then
    return
  fi

  echo -e "\n${BLUE}🔧 Applying Android CPU compatibility patch for pip...${NC}"

  # Find pip's tags.py across all possible Python versions
  TAGS_FILES=$(find /data/data/com.termux/files/usr/lib/ -name "tags.py" -path "*/pip/*" 2>/dev/null)

  if [ -z "$TAGS_FILES" ]; then
    echo -e "  ${YELLOW}⚠ Could not find pip tags.py — skipping patch${NC}"
    return
  fi

  for TAGS_FILE in $TAGS_FILES; do
    echo -e "  Patching: $TAGS_FILE"

    # Check if already patched
    if grep -q "armv8l" "$TAGS_FILE" 2>/dev/null; then
      echo -e "  ${GREEN}✓ Already patched${NC}"
      continue
    fi

    # Backup original
    cp "$TAGS_FILE" "${TAGS_FILE}.bak" 2>/dev/null || true

    # Apply patch: add armv8l and other missing ARM variants to the android_platforms mapping
    python3 - "$TAGS_FILE" << 'PATCHEOF'
import sys
import re

filepath = sys.argv[1]
with open(filepath, 'r') as f:
    content = f.read()

# The broken function that causes KeyError: 'armv8l'
# We replace the entire android_platforms function with a fixed version
old_pattern = r'def android_platforms\(\).*?(?=\ndef |\nclass |\Z)'

new_function = '''def android_platforms():
    """
    Fixed version: supports all Android CPU architectures including
    armv8l, aarch64, x86_64, i686, and any future variants.
    """
    import platform as _platform
    machine = _platform.machine()

    # Complete mapping of all known Android/Linux CPU names to ABI strings
    abi_map = {
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "arm64-v8a": "aarch64",
        "armv8l": "aarch64",      # <-- THE FIX: armv8l = 64-bit ARM
        "armv8": "aarch64",
        "armv7l": "armeabi_v7a",
        "armv7": "armeabi_v7a",
        "arm": "armeabi_v7a",
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "x86": "x86",
        "i686": "x86",
        "i386": "x86",
    }

    abi = abi_map.get(machine, "aarch64")  # default to aarch64 if unknown

    # Generate platform tags for multiple Android API levels
    for api_level in range(21, 36):
        yield f"android_{api_level}_{abi}"

'''

# Use re.DOTALL to match across multiple lines
fixed_content = re.sub(old_pattern, new_function, content, flags=re.DOTALL)

if fixed_content != content:
    with open(filepath, 'w') as f:
        f.write(fixed_content)
    print("  Patch applied successfully")
else:
    # Fallback: just add armv8l to the existing dict if pattern didn't match
    fixed_content = content.replace(
        '"armv7l": "armeabi_v7a",',
        '"armv7l": "armeabi_v7a",\n        "armv8l": "aarch64",\n        "armv8": "aarch64",'
    )
    with open(filepath, 'w') as f:
        f.write(fixed_content)
    print("  Fallback patch applied")
PATCHEOF

    if [ $? -eq 0 ]; then
      echo -e "  ${GREEN}✓ Patched: $TAGS_FILE${NC}"
    else
      echo -e "  ${YELLOW}⚠ Python patch failed, trying sed fallback...${NC}"
      # Pure bash sed fallback — add armv8l right after armv7l line
      sed -i 's/"armv7l": "armeabi_v7a",/"armv7l": "armeabi_v7a",\n        "armv8l": "aarch64",\n        "armv8": "aarch64",/' "$TAGS_FILE" 2>/dev/null && \
        echo -e "  ${GREEN}✓ Sed patch applied${NC}" || \
        echo -e "  ${RED}✗ All patches failed — will try pip_install workaround${NC}"
    fi
  done

  # Also patch sysconfig if needed
  SYSCONFIG_FILES=$(find /data/data/com.termux/files/usr/lib/python*/sysconfig* -name "*.py" 2>/dev/null | head -5)
  for SC_FILE in $SYSCONFIG_FILES; do
    if grep -q '"armv7l": "armeabi_v7a"' "$SC_FILE" 2>/dev/null && ! grep -q '"armv8l"' "$SC_FILE" 2>/dev/null; then
      sed -i 's/"armv7l": "armeabi_v7a",/"armv7l": "armeabi_v7a",\n        "armv8l": "aarch64",/' "$SC_FILE" 2>/dev/null && \
        echo -e "  ${GREEN}✓ Patched sysconfig: $SC_FILE${NC}" || true
    fi
  done

  echo -e "  ${GREEN}✓ Android CPU patch complete${NC}"
}

# ── Safe pip install that handles the armv8l error as fallback ──
safe_pip_install() {
  local pkg="$1"
  local quiet="${2:---quiet}"

  # Method 1: Normal pip
  if pip install "$pkg" $quiet 2>/dev/null; then
    return 0
  fi

  # Method 2: pip3
  if pip3 install "$pkg" $quiet 2>/dev/null; then
    return 0
  fi

  # Method 3: python -m pip (bypasses some shell issues)
  if $PYTHON -m pip install "$pkg" $quiet 2>/dev/null; then
    return 0
  fi

  # Method 4: force reinstall
  if $PYTHON -m pip install "$pkg" --force-reinstall $quiet 2>/dev/null; then
    return 0
  fi

  return 1
}

install_system_deps_termux() {
  echo -e "\n${BLUE}📦 Installing system packages via pkg...${NC}"
  pkg update -y 2>/dev/null || true

  # Core packages only — skip rust (too large, often fails on mobile)
  PKGS=("python" "python-pip" "ffmpeg" "git" "curl" "clang" "libffi" "openssl" "libjpeg-turbo" "libpng")
  for p in "${PKGS[@]}"; do
    if pkg list-installed 2>/dev/null | grep -q "^$p/"; then
      echo -e "  ${GREEN}✓ $p already installed${NC}"
    else
      echo -e "  Installing $p..."
      pkg install -y "$p" 2>/dev/null || echo -e "  ${YELLOW}⚠ Could not install $p, skipping${NC}"
    fi
  done
}

install_system_deps_linux() {
  echo -e "\n${BLUE}📦 Checking system packages...${NC}"

  if check_cmd apt-get; then
    INSTALL_CMD="sudo apt-get install -y"
    PKGS=("python3" "python3-pip" "ffmpeg" "git" "curl" "build-essential" "libffi-dev" "libssl-dev")
  elif check_cmd dnf; then
    INSTALL_CMD="sudo dnf install -y"
    PKGS=("python3" "python3-pip" "ffmpeg" "git" "curl" "gcc" "libffi-devel" "openssl-devel")
  elif check_cmd pacman; then
    INSTALL_CMD="sudo pacman -S --noconfirm"
    PKGS=("python" "python-pip" "ffmpeg" "git" "curl" "base-devel" "libffi" "openssl")
  else
    echo -e "${YELLOW}⚠ Unknown package manager. Please install python3, ffmpeg, git manually.${NC}"
    return
  fi

  for p in "${PKGS[@]}"; do
    $INSTALL_CMD "$p" 2>/dev/null || echo -e "  ${YELLOW}⚠ Could not install $p${NC}"
  done
}

setup_python_env() {
  echo -e "\n${BLUE}🐍 Setting up Python environment...${NC}"

  if check_cmd python3; then
    PYTHON=python3
  elif check_cmd python; then
    PYTHON=python
  else
    echo -e "${RED}✗ Python not found!${NC}"
    exit 1
  fi

  PYVER=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  echo -e "  ${GREEN}✓ Python $PYVER${NC}"

  # Upgrade pip safely (don't break if it fails)
  $PYTHON -m pip install --upgrade pip 2>/dev/null || true
}

install_python_deps() {
  echo -e "\n${BLUE}📚 Installing Python dependencies...${NC}"
  echo -e "  Installing core packages needed to run ClipAI...\n"

  CORE_PKGS=("flask" "flask-cors" "yt-dlp" "requests" "tqdm" "colorama" "python-dotenv")
  MEDIA_PKGS=("moviepy" "Pillow" "numpy")
  AI_PKGS=("gTTS" "openai-whisper" "transformers")

  echo -e "  ${CYAN}── Core packages ──${NC}"
  for pkg in "${CORE_PKGS[@]}"; do
    # Check if already importable
    import_name=$(echo "$pkg" | tr '-' '_' | tr '[:upper:]' '[:lower:]' | sed 's/python_//')
    if $PYTHON -c "import $import_name" 2>/dev/null; then
      echo -e "    ${GREEN}✓ $pkg already installed${NC}"
    else
      echo -ne "    Installing $pkg... "
      if safe_pip_install "$pkg"; then
        echo -e "${GREEN}✓${NC}"
      else
        echo -e "${YELLOW}⚠ failed${NC}"
      fi
    fi
  done

  echo -e "\n  ${CYAN}── Media packages ──${NC}"
  for pkg in "${MEDIA_PKGS[@]}"; do
    import_name=$(echo "$pkg" | tr '[:upper:]' '[:lower:]')
    if $PYTHON -c "import $import_name" 2>/dev/null; then
      echo -e "    ${GREEN}✓ $pkg already installed${NC}"
    else
      echo -ne "    Installing $pkg... "
      if safe_pip_install "$pkg"; then
        echo -e "${GREEN}✓${NC}"
      else
        echo -e "${YELLOW}⚠ failed (optional)${NC}"
      fi
    fi
  done

  echo -e "\n  ${CYAN}── AI packages (optional, heavier) ──${NC}"
  echo -e "  ${YELLOW}These are optional. ClipAI works without them using FFmpeg only.${NC}"
  for pkg in "${AI_PKGS[@]}"; do
    echo -ne "    Installing $pkg... "
    if safe_pip_install "$pkg"; then
      echo -e "${GREEN}✓${NC}"
    else
      echo -e "${YELLOW}⚠ failed (will use basic mode)${NC}"
    fi
  done
}

setup_directories() {
  echo -e "\n${BLUE}📁 Setting up directories...${NC}"
  mkdir -p uploads clips logs models/weights
  echo -e "  ${GREEN}✓ uploads/, clips/, logs/, models/weights/${NC}"
}

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

check_ffmpeg() {
  echo -e "\n${BLUE}🎬 FFmpeg...${NC}"
  if check_cmd ffmpeg; then
    FFVER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    echo -e "  ${GREEN}✓ FFmpeg $FFVER${NC}"
  else
    echo -e "  ${RED}✗ FFmpeg not found!${NC}"
    echo -e "  ${YELLOW}Run: pkg install ffmpeg${NC}"
  fi
}

verify_install() {
  echo -e "\n${BLUE}🔍 Verifying installation...${NC}"
  if $PYTHON -c "import flask" 2>/dev/null; then
    echo -e "  ${GREEN}✓ Flask — OK${NC}"
  else
    echo -e "  ${RED}✗ Flask missing — ClipAI cannot start!${NC}"
    echo -e "  ${YELLOW}Try manually: pip install flask${NC}"
  fi

  if $PYTHON -c "import yt_dlp" 2>/dev/null; then
    echo -e "  ${GREEN}✓ yt-dlp — OK (URL downloading enabled)${NC}"
  else
    echo -e "  ${YELLOW}⚠ yt-dlp missing — URL downloading disabled${NC}"
  fi

  if check_cmd ffmpeg; then
    echo -e "  ${GREEN}✓ FFmpeg — OK (video processing enabled)${NC}"
  else
    echo -e "  ${RED}✗ FFmpeg missing — video processing disabled${NC}"
  fi

  if $PYTHON -c "import whisper" 2>/dev/null; then
    echo -e "  ${GREEN}✓ Whisper — OK (AI mode enabled)${NC}"
  else
    echo -e "  ${YELLOW}⚠ Whisper missing — running in basic mode (FFmpeg only)${NC}"
  fi
}

final_message() {
  IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ip route get 1 2>/dev/null | awk '{print $7}' | head -1 || echo "")

  echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${GREEN}  ✅ ClipAI Installation Complete!${NC}"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
  echo -e "${BOLD}  Start the app:${NC}"
  echo -e "  ${CYAN}bash start.sh${NC}"
  echo ""
  echo -e "${BOLD}  Open in your Android browser:${NC}"
  echo -e "  ${CYAN}http://localhost:5000${NC}"
  if [ -n "$IP" ] && [ "$IP" != "localhost" ]; then
    echo -e "  ${CYAN}http://$IP:5000${NC}  ← from other devices on WiFi"
  fi
  echo ""
}

# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
banner
detect_env

# Install system packages
case $ENV in
  termux) install_system_deps_termux ;;
  linux)  install_system_deps_linux ;;
  mac)    echo -e "${YELLOW}macOS: ensure ffmpeg installed via: brew install ffmpeg${NC}" ;;
esac

# CRITICAL: Fix pip before trying to install anything
fix_pip_android_arch

# Now install Python packages
setup_python_env
install_python_deps
setup_directories
check_ffmpeg
create_config
verify_install
final_message
