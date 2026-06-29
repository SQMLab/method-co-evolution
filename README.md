# Understanding Method-Level Test Code Evolution

This repository supports an empirical study of method-level test code evolution. It evaluates test method history tracking, production-to-test mapping, and downstream analyses of revision frequency and test smells.

## Research Questions

**RQ1: Can existing history tracking tools effectively track test method revision histories?**  
We evaluate state-of-the-art method history tracking tools using a manually constructed oracle of 120 test methods from 40 open-source Java projects.

**RQ2: What is the most accurate approach for method-level production-to-test mapping?**  
We evaluate static analysis-based mapping techniques using existing benchmarks and a newly created oracle for 20 projects.

**RQ3: Are test methods revised less frequently?**  
Using the most effective history tracking and mapping approaches, we compare revision frequencies between test methods and the production methods they exercise.

**RQ4: Are test smells associated with high revisions?**  
We study whether test smells are more common in test methods that accumulate more revisions than their corresponding production methods.

Ground-truth datasets for RQ1 and RQ2 are documented in [data/ground-truth.md](data/ground-truth.md).

## Prerequisites

- Python 3.12+
- Java 21
- Maven 3.6+
- Git

## Project Layout

| Path | Role |
|------|------|
| `method-history-collector/` | Python package exposing `mhc`, the main collection CLI |
| `method-parser/` | JavaParser-based Maven module for method, class, and callgraph extraction |
| `co-evolution/` | Python package exposing `ptc-llm`, `ptc-history-viewer`, `ptc-testlinker`, and `ptc-sbatch` |
| `co-evolution/src/ptc/testlinker/` | Neural TestLinker integration and model pipeline notes |
| `jnose-adapter/` | Executable wrapper used by the `mhc test-smell` workflow |
| `scripts/` | Build, Slurm, and maintenance helpers |
| `config/` and `docs/` | Artifact-detection and experiment configuration references |

Each tracked README is a focused reference for its module. Generated cache READMEs, such as `.pytest_cache/README.md`, are not part of the project documentation.

## Workspace Layout

`ME_WORKSPACE_DIRECTORY` stores experimental data and generated artifacts. Multiple experiments can run concurrently under `workspace/experiment/<name>/` by changing `ME_EXPERIMENT_NAME`, which is useful for different project sets, tool configurations, or study runs.

Example workspace layout:

```text
workspace/
  jar/
    method-parser.jar
  experiment/
    main/
      aggregate                      Concatenated individual project csvs or resultant csv across project.
      project.csv                    Project index and repository metadata for the experiment.
      method/                        Method index CSVs extracted from each project.
      method-code/                   Method source and code metadata for downstream linking and filtering.
      method-history/                Method revision count.
      method-history-gz/             Compressed method history archives.
      class/                         Class index CSVs extracted from each project.
      callgraph/                     Method call graph (fan-out).
      t2p-candidate-expanded/        Expanded production-to-test mapping candidates.
      t2p-candidate-filtered/        Filtered production-to-test candidates used by linkers.
      t2p-tech/                      Per-technique mapping predictions and intermediate technique outputs.
      t2p-link/                      Final production-to-test links by strategy/technique.
      t2p-change/                    Linked production/test revision comparison data.
      t2p-revision-review/           Sampled or review-oriented revision comparison data.
      test-smell/                    Test smell detector outputs.
      t2p-test-smell/                Test smells joined with production-to-test links.
      t2p-test-smell-with-revision/  Linked test smell rows with revision-group information.
```

The Python packages load `.env` from the repository root. A typical local file contains:

```bash
# Repository root used by scripts to resolve project-relative paths.
ME_PROJECT_DIRECTORY=/path/to/method-co-evolution

# Shared workspace for experimental data and generated artifacts.
ME_WORKSPACE_DIRECTORY=/path/to/method-co-evolution/workspace

# Active experiment under ME_WORKSPACE_DIRECTORY/experiment/.
ME_EXPERIMENT_NAME=main

# Optional: faster repository checkout and GitHub API access.
GITHUB_API_KEY=ghp_...

# Optional: store method histories outside the main workspace.
ME_HISTORY_DIRECTORY=/scratch/method-co-evolution/history

# Optional: Hugging Face access for local model downloads or gated models.
HF_TOKEN=hf_...

# Optional: OpenAI access for LLM-based linking experiments.
OPENAI_API_KEY=sk_...
```

## Setup

Run these commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ./method-history-collector
pip install -e ./co-evolution

# Optional backends
pip install -e './co-evolution[llm]'
pip install -e './co-evolution[testlinker]'
```

Build the Java parser and copy the executable JAR into `WORKSPACE_DIRECTORY/jar/`:

```bash
scripts/build-method-parser.sh
```

For the jNose test-smell workflow, also build `jnose-core` and `jnose-adapter`; see [jnose-adapter/README.md](jnose-adapter/README.md).

## First Pipeline Run

Create or confirm the experiment project index:

```text
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/project.csv
```

The file must include a `project` column and the repository metadata expected by the collection commands.

Run a minimal extraction for one project:

```bash
mhc method-scan \
  --workspace-directory "$ME_WORKSPACE_DIRECTORY" \
  --experiment-name "$ME_EXPERIMENT_NAME" \
  --project "checkstyle"

mhc class-scan \
  --workspace-directory "$ME_WORKSPACE_DIRECTORY" \
  --experiment-name "$ME_EXPERIMENT_NAME" \
  --project "checkstyle"

mhc method-callgraph \
  --workspace-directory "$ME_WORKSPACE_DIRECTORY" \
  --experiment-name "$ME_EXPERIMENT_NAME" \
  --tool-name methodParser \
  --project "checkstyle"

mhc method-code \
  --workspace-directory "$ME_WORKSPACE_DIRECTORY" \
  --experiment-name "$ME_EXPERIMENT_NAME" \
  --project "checkstyle"
```

Core outputs are written under:

```text
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/method/<project>.csv
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/class/<project>.csv
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/callgraph/<project>.csv
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/fanin/<project>.csv
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/method-code/<project>.csv
```

Then run history collection, candidate generation, LLM linking, or TestLinker depending on the experiment.

To review histories in the local UI, run:

```bash
scripts/history-viewer.sh
```

The helper serves `ptc-history-viewer` at `http://127.0.0.1:8765`; see [scripts/README.md](scripts/README.md#history-viewersh) for details.

## Pipeline Overview

```text
project.csv
  -> mhc method-scan       -> method/<project>.csv
  -> mhc class-scan        -> class/<project>.csv
  -> mhc method-callgraph  -> callgraph/<project>.csv and fanin/<project>.csv
  -> mhc method-history    -> history/<tool>/<project>/
  -> mhc method-code       -> method-code/<project>.csv
  -> generator scripts     -> t2p-candidate-filtered/ and related candidate datasets
  -> ptc-llm               -> llm/<input-kind>/<model>/
  -> ptc-testlinker        -> testlinker/output/<model>/
  -> ptc-history-viewer    -> local browser review UI
```

Paths in the overview are relative to `WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/` unless noted otherwise.

## Common Documentation

- [method-history-collector/README.md](method-history-collector/README.md) for `mhc` commands and experiment path defaults.
- [method-parser/README.md](method-parser/README.md) for Java build steps and CSV schemas.
- [co-evolution/README.md](co-evolution/README.md) for LLM linking, history viewer, TestLinker entrypoints, and Slurm command expansion.
- [co-evolution/src/ptc/testlinker/README.md](co-evolution/src/ptc/testlinker/README.md) for neural TestLinker setup and model artifacts.
- [scripts/README.md](scripts/README.md) for helper scripts and Slurm usage.
- [jnose-adapter/README.md](jnose-adapter/README.md) for test-smell adapter build steps.
