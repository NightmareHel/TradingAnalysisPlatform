#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "First-time setup — installing dependencies..."
    echo ""
    bash setup.sh
    if [ $? -ne 0 ]; then
        echo ""
        echo "Setup failed. Please fix the issues above and try again."
        read -p "Press Enter to close..."
        exit 1
    fi
fi

source venv/bin/activate
echo "Starting Stock Predictor..."
echo "The app will open in your browser at http://localhost:8501"
echo ""
streamlit run app.py --server.headless true
