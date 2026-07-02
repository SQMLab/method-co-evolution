#!/usr/bin/env bash

set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_directory"

if ! command -v latexmk >/dev/null 2>&1; then
  echo "Error: latexmk is not installed or is not available in PATH." >&2
  exit 1
fi

build_directory="$script_directory/build"
mkdir -p "$build_directory"

latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$build_directory" main.tex

echo "Built $build_directory/main.pdf"
