#!/bin/bash
#
# DDI Toolkit - Setup Script
# Creates virtual environment and installs dependencies
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
DDI_SCRIPT="$SCRIPT_DIR/ddi"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}"
echo "  ╔═══════════════════════════════════════════════════╗"
echo "  ║           DDI TOOLKIT - SETUP                     ║"
echo "  ╚═══════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python version
echo -e "${BOLD}[1/3] Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}  Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}  Error: Python 3.8+ required. Found ${PYTHON_VERSION}${NC}"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Python ${PYTHON_VERSION} found"

# Create virtual environment
echo -e "\n${BOLD}[2/3] Setting up virtual environment...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo -e "  ${GREEN}✓${NC} Virtual environment created"
else
    echo -e "  ${YELLOW}○${NC} Virtual environment already exists"
fi

# Activate and install dependencies
echo -e "\n${BOLD}[3/3] Installing dependencies...${NC}"
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
    echo -e "  ${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${RED}  Error: requirements.txt not found${NC}"
    exit 1
fi

# Make main script executable
chmod +x "$DDI_SCRIPT"

# Create output directory
mkdir -p "$SCRIPT_DIR/output"

echo -e "\n${GREEN}════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════${NC}"
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
