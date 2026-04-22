#!/usr/bin/env bash

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say() {
  printf "%b\n" "$1"
}

prompt() {
  local message="$1"
  local default_value="${2:-}"
  local value
  if [[ -n "$default_value" ]]; then
    read -r -p "$message [$default_value]: " value
    printf "%s" "${value:-$default_value}"
  else
    read -r -p "$message: " value
    printf "%s" "$value"
  fi
}

confirm() {
  local message="$1"
  local answer
  read -r -p "$message [y/N]: " answer
  [[ "$answer" =~ ^[Yy]$ ]]
}

require_dir() {
  if [[ ! -d "$1" ]]; then
    say "${RED}✗ Directory does not exist: $1${NC}"
    exit 1
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    say "${RED}✗ Missing required command: $1${NC}"
    exit 1
  fi
}

install_pi() {
  require_command pi
  local scope="$1"
  local project_dir="$2"

  if [[ "$scope" == "global" ]]; then
    say "${YELLOW}Installing for Pi globally...${NC}"
    pi install "$REPO_DIR"
  else
    require_dir "$project_dir"
    say "${YELLOW}Installing for Pi in project: $project_dir${NC}"
    (cd "$project_dir" && pi install -l "$REPO_DIR")
  fi

  say "${GREEN}✓ Pi installation complete${NC}"
}

install_claude() {
  local plugin_root="$HOME/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/latest"
  say "${YELLOW}Installing for Claude Code using a symlinked local checkout...${NC}"
  mkdir -p "$(dirname "$plugin_root")"
  rm -rf "$plugin_root"
  ln -s "$REPO_DIR" "$plugin_root"
  say "${GREEN}✓ Claude Code installation complete${NC}"
  say "${YELLOW}Note:${NC} this preserves the existing Claude plugin layout via ${plugin_root}"
}

install_opencode() {
  local project_dir="$1"
  require_dir "$project_dir"
  require_command rsync
  say "${YELLOW}Installing OpenCode resources into: $project_dir${NC}"
  mkdir -p "$project_dir/.opencode"

  if [[ -d "$REPO_DIR/.opencode" ]]; then
    rsync -a "$REPO_DIR/.opencode/" "$project_dir/.opencode/"
  fi

  say "${GREEN}✓ OpenCode installation complete${NC}"
}

say "${CYAN}======================================================${NC}"
say "${CYAN}   Rafayel's Engineering Toolkit Installer            ${NC}"
say "${CYAN}======================================================${NC}"
say ""
say "Repository: $REPO_DIR"
say ""
say "Choose target agent:"
say "  1) Pi"
say "  2) Claude Code"
say "  3) OpenCode"
say "  4) Install for all supported agents"
say "  5) Cancel"
say ""

choice="$(prompt 'Enter your choice [1-5]')"

if ! confirm "Proceed with installation changes?"; then
  say "Installation cancelled."
  exit 0
fi

case "$choice" in
  1)
    say ""
    say "Pi install scope:"
    say "  1) Global"
    say "  2) Project-local"
    scope_choice="$(prompt 'Enter your choice [1-2]')"
    if [[ "$scope_choice" == "1" ]]; then
      install_pi global ""
    elif [[ "$scope_choice" == "2" ]]; then
      target_project="$(prompt 'Project directory' "$PWD")"
      install_pi local "$target_project"
    else
      say "${RED}Invalid Pi scope selection${NC}"
      exit 1
    fi
    ;;
  2)
    install_claude
    ;;
  3)
    target_project="$(prompt 'Project directory' "$PWD")"
    install_opencode "$target_project"
    ;;
  4)
    install_pi global ""
    install_claude
    target_project="$(prompt 'OpenCode project directory' "$PWD")"
    install_opencode "$target_project"
    ;;
  5)
    say "Installation cancelled."
    exit 0
    ;;
  *)
    say "${RED}Invalid choice${NC}"
    exit 1
    ;;
esac

say ""
say "${GREEN}Done.${NC}"
say "Initialize memory once with:"
say "  ${CYAN}${PYTHON_FOR_RAFAYELS_ENGINEERING:-python3} $REPO_DIR/skills/memory/scripts/memory.py init${NC}"
