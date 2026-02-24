#!/usr/bin/env bash
#
# HeyDucky installer for macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/IdanG7/HeyDucky/master/install.sh | bash
#
set -euo pipefail

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()  { echo -e "${BOLD}${GREEN}==>${RESET} ${BOLD}$1${RESET}"; }
warn()  { echo -e "${YELLOW}warning:${RESET} $1"; }
fail()  { echo -e "${RED}error:${RESET} $1"; exit 1; }

# -------------------------------------------------------------------
# Preflight checks
# -------------------------------------------------------------------

echo ""
echo -e "${BOLD}HeyDucky Installer${RESET}"
echo -e "${DIM}Your AI rubber duck that actually talks back${RESET}"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
    fail "This installer is for macOS only. On Linux, use: pip install heyducky"
fi

# -------------------------------------------------------------------
# Homebrew
# -------------------------------------------------------------------

if ! command -v brew &>/dev/null; then
    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for this session (Apple Silicon vs Intel)
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# -------------------------------------------------------------------
# System dependencies
# -------------------------------------------------------------------

info "Installing system dependencies..."
brew install portaudio 2>/dev/null || true

# -------------------------------------------------------------------
# Python
# -------------------------------------------------------------------

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || echo "(0, 0)")
        major=$(echo "$ver" | grep -o '[0-9]*' | head -1)
        minor=$(echo "$ver" | grep -o '[0-9]*' | tail -1)
        if [[ "$major" -ge 3 ]] && [[ "$minor" -ge 10 ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    info "Installing Python 3.12 via Homebrew..."
    brew install python@3.12
    PYTHON="python3.12"
fi

info "Using $($PYTHON --version)"

# -------------------------------------------------------------------
# pipx
# -------------------------------------------------------------------

if ! command -v pipx &>/dev/null; then
    info "Installing pipx..."
    brew install pipx
    pipx ensurepath 2>/dev/null || true
fi

# -------------------------------------------------------------------
# Install ducky
# -------------------------------------------------------------------

info "Installing HeyDucky..."

# If running from the repo directory, install from local source
if [[ -f "pyproject.toml" ]] && grep -q "heyducky" pyproject.toml 2>/dev/null; then
    pipx install --python "$PYTHON" ".[tts]" --force
else
    pipx install --python "$PYTHON" "heyducky[tts]" --force
fi

# -------------------------------------------------------------------
# Verify
# -------------------------------------------------------------------

if ! command -v ducky &>/dev/null; then
    warn "ducky not found on PATH. You may need to restart your shell."
    warn "Or run: pipx ensurepath && source ~/.zshrc"
fi

# -------------------------------------------------------------------
# First-run setup
# -------------------------------------------------------------------

echo ""
info "Installation complete!"
echo ""
echo -e "  ${BOLD}Quick start:${RESET}"
echo ""
echo -e "    ${DIM}# First-time config (set your Anthropic API key)${RESET}"
echo -e "    ducky --setup"
echo ""
echo -e "    ${DIM}# Chat about a project${RESET}"
echo -e "    ducky --project /path/to/your/code"
echo ""
echo -e "    ${DIM}# Debug a Python script${RESET}"
echo -e "    ducky script.py"
echo ""
echo -e "    ${DIM}# Attach to a remote debugger${RESET}"
echo -e "    ducky --attach 192.168.1.50:5678 --language python"
echo ""

read -rp "Run setup wizard now? [Y/n] " answer
if [[ "${answer:-Y}" =~ ^[Yy]$ ]]; then
    ducky --setup
fi
