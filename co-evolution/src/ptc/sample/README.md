# T2P Ground Truth Sampler

Regenerate per-project test-to-production ground truth CSV files for labeling.
The sampler preserves existing working rows, can add fresh sampled test methods,
normalizes the ground truth schema, and updates the `candidate` column from the
expanded candidate files.

## Command

```bash
PYTHONPATH=co-evolution/src:method-history-collector/src \
python -m ptc.sample.sample_t2p_ground_truth \
  --workspace-directory workspace \
  --experiment-name t2plinker \
  --project-index ":" \
  --sample-count-per-project 20 \
  --t2p-ground-truth-dir data/t2plinker/t2p-ground-truth
```

To only normalize/update existing rows without adding any fresh sampled test
methods, pass `0`:

```bash
PYTHONPATH=co-evolution/src:method-history-collector/src \
python -m ptc.sample.sample_t2p_ground_truth \
  --workspace-directory workspace \
  --experiment-name t2plinker \
  --project-index ":" \
  --sample-count-per-project 0 \
  --t2p-ground-truth-dir data/t2plinker/t2p-ground-truth \
  --add-missing-candidates
```

## Inputs And Outputs

- Input ground truth: `--t2p-ground-truth-dir`
- Expanded candidates: `workspace/experiment/{experiment}/t2p-candidate-expanded`
- Method metadata: `workspace/experiment/{experiment}/method`
- Output ground truth: `workspace/experiment/{experiment}/t2p-ground-truth`
- Temporary output: `workspace/experiment/{experiment}/.t2p-ground-truth`

## Options

- `--workspace-directory`: workspace root containing the `experiment` directory.
- `--experiment-name`: experiment name under the workspace.
- `--projects`: comma-separated project names. Defaults to `ME_PROJECTS`.
- `--project-index`: Python-style project index or slice from `project.csv`, such as `0`, `1:5`, or `:`.
- `--sample-count-per-project`: number of test methods to include per project. Use `0` to add no fresh rows.
- `--t2p-ground-truth-dir`: existing ground truth directory to preserve and update.
- `--exclude-test-artifact-regex`: regex for excluding matching test artifacts from fresh random additions.
- `--update-columns`: comma-separated columns to refresh from method metadata on reused rows, excluding protected fields. `candidate` may be included; it is recomputed from expanded candidates.
- `--add-missing-candidates`: add expanded-candidate rows for non-empty `from_url` values already present in the input ground truth.

## Candidate Column

The output schema includes `candidate` immediately after `to_call_depth`.

- `candidate = 1`: the row exists in the matching expanded candidate CSV.
- `candidate = 0`: the row is not present, or the expanded candidate CSV is missing.

Rows are matched by `project`, `from_url`, and `to_url`.
