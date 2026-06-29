#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================="
echo "  Stock Predictor — Setup"
echo "========================================="
echo ""

# 1. Check Python 3.11+
echo -n "Checking Python... "
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        echo -e "${GREEN}Python $PY_VERSION found${NC}"
    else
        echo -e "${RED}Python $PY_VERSION found, but 3.11+ is required${NC}"
        echo ""
        echo "Install Python 3.11+ via Homebrew:"
        echo "  brew install python@3.11"
        echo ""
        echo "Or download from: https://www.python.org/downloads/"
        exit 1
    fi
else
    echo -e "${RED}Python 3 not found${NC}"
    echo ""
    echo "Install Python 3.11+ via Homebrew:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "  brew install python@3.11"
    echo ""
    echo "Or download from: https://www.python.org/downloads/"
    exit 1
fi

# 2. Check Xcode Command Line Tools
echo -n "Checking Xcode Command Line Tools... "
if xcode-select -p &>/dev/null; then
    echo -e "${GREEN}installed${NC}"
else
    echo -e "${YELLOW}not found — installing...${NC}"
    xcode-select --install
    echo ""
    echo "Please complete the Xcode Command Line Tools installation,"
    echo "then re-run this setup script."
    exit 1
fi

# 3. Create virtual environment
if [ ! -d "venv" ]; then
    echo -n "Creating virtual environment... "
    python3 -m venv venv
    echo -e "${GREEN}done${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists — reusing${NC}"
fi

# 4. Install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}Dependencies installed${NC}"

# 5. Create data directory
mkdir -p data

# 6. Make run.command executable
chmod +x run.command

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Double-click 'run.command' to launch the app"
echo "  2. Enter your API keys in the Settings page"
echo "  3. Start analyzing stocks!"
echo ""
