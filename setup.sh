#!/bin/bash
#
# DDI Toolkit - Setup Script
# Creates virtual environment and installs dependencies
#
# Compatible with: macOS, Ubuntu, RHEL/CentOS, WSL
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DDI_SCRIPT="$SCRIPT_DIR/ddi"

# Colors (with fallback for minimal terminals)
if [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'
    BOLD='\033[1m'
else
    RED=''
    GREEN=''
    YELLOW=''
    CYAN=''
    NC=''
    BOLD=''
fi

echo -e "${CYAN}"
echo "  +-----------------------------------------------------+"
echo "  |           DDI TOOLKIT - SETUP                       |"
echo "  +-----------------------------------------------------+"
echo -e "${NC}"

# Check Python version
echo -e "${BOLD}[1/4] Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  Error: Python 3 is required but not installed.${NC}"
    echo -e "  Install with:"
    echo -e "    RHEL/CentOS: sudo yum install python3 python3-pip python3-venv"
    echo -e "    Ubuntu:      sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}  Error: Python 3.8+ required. Found ${PYTHON_VERSION}${NC}"
    exit 1
fi

echo -e "  ${GREEN}[OK]${NC} Python ${PYTHON_VERSION} found"

# Create virtual environment
echo -e "\n${BOLD}[2/4] Setting up virtual environment...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    # Check if venv module is available (may need python3-venv on RHEL/Ubuntu)
    if ! python3 -c "import venv" 2>/dev/null; then
        echo -e "${RED}  Error: Python venv module not found.${NC}"
        echo -e "  Install with:"
        echo -e "    RHEL/CentOS: sudo yum install python3-venv"
        echo -e "    Ubuntu:      sudo apt install python3-venv"
        exit 1
    fi
    python3 -m venv "$VENV_DIR"
    echo -e "  ${GREEN}[OK]${NC} Virtual environment created"
else
    echo -e "  ${YELLOW}[--]${NC} Virtual environment already exists"
fi

# Activate and install dependencies
echo -e "\n${BOLD}[3/4] Installing Python dependencies...${NC}"
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
    echo -e "  ${GREEN}[OK]${NC} Dependencies installed"
else
    echo -e "${RED}  Error: requirements.txt not found${NC}"
    exit 1
fi

# Make main script executable
chmod +x "$DDI_SCRIPT"

# Create output directory
mkdir -p "$SCRIPT_DIR/output"

# Install Node.js dependencies (marp-cli for presentations) - OPTIONAL
echo -e "\n${BOLD}[4/4] Installing presentation tools (optional)...${NC}"
if command -v npm &> /dev/null; then
    if ! command -v marp &> /dev/null; then
        # Try local install first (no sudo needed), fall back to noting skip
        if npm install -g @marp-team/marp-cli --silent 2>/dev/null; then
            echo -e "  ${GREEN}[OK]${NC} marp-cli installed (for presentations)"
        else
            echo -e "  ${YELLOW}[--]${NC} marp-cli install failed (may need sudo)"
            echo -e "       Run: sudo npm install -g @marp-team/marp-cli"
        fi
    else
        echo -e "  ${YELLOW}[--]${NC} marp-cli already installed"
    fi
else
    echo -e "  ${YELLOW}[--]${NC} npm not found - skipping marp-cli (optional)"
    echo -e "       Install Node.js to enable PowerPoint/PDF export"
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}======================================================${NC}"
echo
echo -e "  To start DDI Toolkit:"
echo
echo -e "    ${CYAN}source .venv/bin/activate${NC}    # Activate venv"
echo -e "    ${CYAN}./ddi${NC}                        # Run toolkit"
echo
echo -e "  Or run directly:"
echo
echo -e "    ${CYAN}.venv/bin/python ./ddi${NC}"
echo
echo -e "  First run will prompt for InfoBlox configuration."
echo
echo -e "  To generate presentations:"
echo
echo -e "    ${CYAN}marp docs/DDI_Toolkit_Presentation.md --pptx -o DDI_Toolkit.pptx${NC}"
echo -e "    ${CYAN}marp docs/DDI_Toolkit_Presentation.md --pdf -o DDI_Toolkit.pdf${NC}"
echo
