#!/usr/bin/env bash
# Gitflow helper — inspect branch state (no destructive operations).
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
  cat <<'EOF'
Usage: scripts/sh/gitflow.sh <command>

Commands:
  status    Show current branch, gitflow type, and divergence from main/develop
  check     Validate branch name against gitflow prefixes (exit 1 if invalid)
  branches  List local feature/* branches and whether they are merged into develop
  cleanup   Delete local feature/* branches already merged into develop (dry-run with --dry-run)

Examples:
  ./scripts/sh/gitflow.sh status
  ./scripts/sh/gitflow.sh check
  ./scripts/sh/gitflow.sh branches
  ./scripts/sh/gitflow.sh cleanup --dry-run
  ./scripts/sh/gitflow.sh cleanup
EOF
}

current_branch() {
  git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown"
}

branch_type() {
  local branch="$1"
  case "$branch" in
    main|master) echo "main" ;;
    develop) echo "develop" ;;
    feature/*) echo "feature" ;;
    release/*) echo "release" ;;
    hotfix/*) echo "hotfix" ;;
    *) echo "other" ;;
  esac
}

count_ahead_behind() {
  local base="$1"
  if ! git rev-parse --verify "$base" >/dev/null 2>&1; then
    echo "n/a"
    return
  fi
  local ahead behind
  ahead=$(git rev-list --count "$base..HEAD" 2>/dev/null || echo "?")
  behind=$(git rev-list --count "HEAD..$base" 2>/dev/null || echo "?")
  echo "+${ahead}/-${behind}"
}

cmd_status() {
  local branch type
  branch=$(current_branch)
  type=$(branch_type "$branch")

  echo "=== Gitflow status ==="
  echo "Branch:  $branch"
  echo "Type:    $type"

  if git rev-parse --verify origin/main >/dev/null 2>&1; then
    echo "vs origin/main:    $(count_ahead_behind origin/main)"
  elif git rev-parse --verify main >/dev/null 2>&1; then
    echo "vs main:           $(count_ahead_behind main)"
  fi

  if git rev-parse --verify origin/develop >/dev/null 2>&1; then
    echo "vs origin/develop: $(count_ahead_behind origin/develop)"
  elif git rev-parse --verify develop >/dev/null 2>&1; then
    echo "vs develop:        $(count_ahead_behind develop)"
  else
    echo -e "${YELLOW}develop branch not found — run gitflow bootstrap (see skills/gitflow/SKILL.md)${NC}"
  fi

  echo ""
  echo "Recent commits:"
  git log --oneline -3 2>/dev/null || true

  case "$type" in
    feature)
      echo -e "${GREEN}Expected merge target: develop${NC}"
      ;;
    release|hotfix)
      echo -e "${GREEN}Expected merge targets: main + develop${NC}"
      ;;
    other)
      echo -e "${YELLOW}Not a standard gitflow branch name${NC}"
      ;;
  esac
}

cmd_check() {
  local branch type
  branch=$(current_branch)
  type=$(branch_type "$branch")

  case "$type" in
    main|develop|feature|release|hotfix)
      echo -e "${GREEN}OK${NC}: $branch ($type)"
      exit 0
      ;;
    *)
      echo -e "${RED}INVALID${NC}: $branch is not a gitflow branch"
      echo "Use: main, develop, feature/<name>, release/<version>, hotfix/<name>"
      exit 1
      ;;
  esac
}

develop_ref() {
  if git rev-parse --verify develop >/dev/null 2>&1; then
    echo "develop"
  elif git rev-parse --verify origin/develop >/dev/null 2>&1; then
    echo "origin/develop"
  else
    echo ""
  fi
}

cmd_branches() {
  local base
  base=$(develop_ref)
  if [[ -z "$base" ]]; then
    echo -e "${YELLOW}develop branch not found${NC}"
    exit 1
  fi

  echo "=== Feature branches (merge target: $base) ==="
  local found=0
  while IFS= read -r branch; do
    [[ -z "$branch" ]] && continue
    found=1
    local ahead
    ahead=$(git rev-list --count "$base..$branch" 2>/dev/null || echo "?")
    if [[ "$ahead" == "0" ]]; then
      echo -e "  ${GREEN}synced${NC}   $branch (no commits ahead of $base)"
    elif git merge-base --is-ancestor "$branch" "$base" 2>/dev/null; then
      echo -e "  ${GREEN}merged${NC}   $branch"
    else
      echo -e "  ${YELLOW}open${NC}     $branch (+${ahead} commits)"
    fi
  done < <(git branch --list 'feature/*' | sed 's/^[* ] //')

  if [[ "$found" -eq 0 ]]; then
    echo "  (none)"
  fi
}

cmd_cleanup() {
  local dry_run=0
  if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
  fi

  local base
  base=$(develop_ref)
  if [[ -z "$base" ]]; then
    echo -e "${YELLOW}develop branch not found${NC}"
    exit 1
  fi

  local current deleted=0
  current=$(current_branch)

  while IFS= read -r branch; do
    [[ -z "$branch" ]] && continue
    if ! git merge-base --is-ancestor "$branch" "$base" 2>/dev/null; then
      continue
    fi
    if [[ "$branch" == "$current" ]]; then
      echo -e "${YELLOW}skip${NC} $branch (current branch)"
      continue
    fi
    if [[ "$dry_run" -eq 1 ]]; then
      echo -e "${GREEN}would delete${NC} $branch"
    else
      git branch -d "$branch"
      echo -e "${GREEN}deleted${NC} $branch"
    fi
    deleted=$((deleted + 1))
  done < <(git branch --merged "$base" --list 'feature/*' | sed 's/^[* ] //')

  if [[ "$deleted" -eq 0 ]]; then
    echo "No merged feature branches to clean up."
  fi
}

main() {
  local cmd="${1:-status}"
  case "$cmd" in
    status) cmd_status ;;
    check) cmd_check ;;
    branches) cmd_branches ;;
    cleanup) cmd_cleanup "${2:-}" ;;
    -h|--help|help) usage ;;
    *)
      echo "Unknown command: $cmd" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "${1:-status}"
