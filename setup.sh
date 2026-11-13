#!/usr/bin/env bash
# Ubuntu/Debian bootstrap. Run as a normal user; only apt uses sudo when required.
set -euo pipefail
repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
check_only=false
dry_run=false
skip_system=false
python_exe="${PYTHON:-python3}"
while (($#)); do
  case "$1" in
    --check-only) check_only=true ;;
    --dry-run) dry_run=true ;;
    --skip-system) skip_system=true ;;
    --python) shift; [[ $# -gt 0 ]] || { echo '--python needs an executable' >&2; exit 2; }; python_exe="$1" ;;
    --help|-h)
      printf '%s\n' 'Usage: bash setup.sh [--dry-run|--check-only] [--skip-system] [--python python3.12]'
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
packages=(python3 python3-venv python3-pip texlive-xetex texlive-lang-chinese
  texlive-latex-extra texlive-fonts-recommended fonts-texgyre fonts-noto-cjk)
if "$dry_run"; then
  printf '%s\n' 'Plan: Ubuntu 24.04+ / compatible Debian, Python >=3.11; preserve Codex global settings.'
  if ! "$skip_system" && ! "$check_only"; then
    printf 'Plan: apt-get install missing packages:'; printf ' %s' "${packages[@]}"; printf '\n'
  fi
  printf '%s\n' 'Plan: repo .venv, requirements.txt, actual Chinese/math/TikZ compilation, strict doctor.'
  exit 0
fi
if "$check_only"; then
  if [[ -x "$repo_root/.venv/bin/python" ]]; then python_exe="$repo_root/.venv/bin/python"; fi
  exec "$python_exe" "$repo_root/scripts/doctor.py" --strict
fi
[[ "$(uname -s)" == Linux ]] || { echo 'Use setup.ps1 on Windows. On other systems prepare Python >=3.11 and XeLaTeX manually.' >&2; exit 2; }
if ! "$skip_system"; then
  command -v apt-get >/dev/null || { echo 'No apt-get; use --skip-system after manual environment setup.' >&2; exit 2; }
  missing=()
  for package in "${packages[@]}"; do
    if [[ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" != 'install ok installed' ]]; then
      missing+=("$package")
    fi
  done
  if ((${#missing[@]})); then
    elevate=()
    if [[ "$(id -u)" != 0 ]]; then
      command -v sudo >/dev/null || { echo 'Missing packages require an administrator; sudo is unavailable.' >&2; exit 2; }
      elevate=(sudo)
    fi
    "${elevate[@]}" apt-get update
    "${elevate[@]}" apt-get install -y --no-install-recommends "${missing[@]}"
  fi
fi
command -v "$python_exe" >/dev/null || { echo 'Python unavailable. Install Python >=3.11.' >&2; exit 2; }
"$python_exe" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Python >=3.11 required. Ubuntu 24.04+ is recommended; select an installed interpreter with --python.")'
venv_python="$repo_root/.venv/bin/python"
if [[ ! -x "$venv_python" ]]; then "$python_exe" -m venv "$repo_root/.venv"; fi
"$venv_python" -m pip install --requirement "$repo_root/requirements.txt"
"$venv_python" "$repo_root/scripts/smoke_test.py"
"$venv_python" "$repo_root/scripts/doctor.py" --strict
printf '%s\n' 'Setup completed. Use Codex CLI/available host with this repo and prompts/start-book.md.'
