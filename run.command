#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

clear
echo ""
echo "  ================================================"
echo "    Trading Analysis Platform"
echo "  ================================================"
echo ""

# ── 1. Find Python 3.11+ ────────────────────────────────────────────────────
echo -n "  Checking Python..."
PY_CMD=""
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
        MAJ=$(echo "$VER" | cut -d. -f1)
        MIN=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJ" -ge 3 ] && [ "$MIN" -ge 11 ]; then
            PY_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    echo -e " ${RED}not found${NC}"
    echo ""
    echo -e "  ${BOLD}Python 3.11 or higher is required.${NC}"
    echo ""
    echo "  Download and install it here (takes about 2 minutes):"
    echo ""
    echo "    https://www.python.org/downloads/"
    echo ""
    echo "  After installing, double-click this file again."
    echo ""
    read -p "  Press Enter to close..."
    exit 1
fi
echo -e " ${GREEN}Python $VER${NC}"

# ── 2. Xcode Command Line Tools ─────────────────────────────────────────────
echo -n "  Checking developer tools..."
if ! xcode-select -p &>/dev/null; then
    echo -e " ${YELLOW}installing...${NC}"
    echo ""
    echo "  A dialog box will appear asking you to install developer tools."
    echo "  Click 'Install' and wait for it to finish."
    echo "  Then double-click this file again."
    echo ""
    xcode-select --install 2>/dev/null
    read -p "  Press Enter to close..."
    exit 0
fi
echo -e " ${GREEN}OK${NC}"

# ── 3. Virtual environment ───────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo -n "  Setting up Python environment (first time, ~30 seconds)..."
    "$PY_CMD" -m venv venv
    echo -e " ${GREEN}done${NC}"
fi
source venv/bin/activate

# ── 4. Dependencies ──────────────────────────────────────────────────────────
echo -n "  Checking dependencies..."
pip install -r requirements.txt -q --disable-pip-version-check 2>&1
if [ $? -ne 0 ]; then
    echo -e " ${RED}failed${NC}"
    echo ""
    echo "  Could not install dependencies. Check your internet connection and try again."
    echo ""
    read -p "  Press Enter to close..."
    exit 1
fi
echo -e " ${GREEN}OK${NC}"

# ── 5. Data directory ────────────────────────────────────────────────────────
mkdir -p data

# ── 6. Launch ────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}Starting the app...${NC}"
echo ""
echo "  Your browser will open automatically in a few seconds."
echo "  ─────────────────────────────────────────────────────"
echo "  To STOP the app: close this window."
echo "  ─────────────────────────────────────────────────────"
echo ""

# Open browser after Streamlit has had time to bind
(sleep 4 && open "http://localhost:8501") &

streamlit run app.py --server.headless true

echo ""
echo "  App has stopped."
read -p "  Press Enter to close..."
