#!/bin/bash
module load StdEnv
module load scipy-stack/2025a
module load ipykernel/2025a
module load arrow
module load cuda
module load java/21.0.1

source .venv/bin/activate

# Strip --dry-run from args before passing to python
DRY_RUN=0
ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=1
    else
        ARGS+=("$arg")
    fi
done

if [[ "$DRY_RUN" == "1" ]]; then
    python co-evolution/src/ptc/drac/main.py "${ARGS[@]}"
else
    CMD=$(python co-evolution/src/ptc/drac/main.py "${ARGS[@]}")
    echo "Executing: $CMD" >&2
    eval "$CMD"
fi
