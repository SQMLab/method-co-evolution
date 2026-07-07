# jnose-adapter

`jnose-adapter` is the executable bridge between MHC's `mhc test-smell` workflow and [`jnose-core`](https://github.com/arieslab/jnose-core). MHC prepares CSV rows that pair test files with production files, this adapter runs jNose Core smell detection for those pairs, and MHC postprocesses the raw adapter output into experiment datasets.

This Maven module depends on `br.ufba.jnose:jnose-core:0.8.6`. `jnose-core` is a library JAR and cannot be run directly with `java -jar`, so it must be built and installed first. The adapter then builds a shaded executable JAR with the command-line entry point that MHC expects:

```bash
java -jar jnose-adapter-1.0.0.jar --file <input.csv> --output <output.csv>
```

## Build Order

Run all commands from the repository root.

1. Clone or check out [`arieslab/jnose-core`](https://github.com/arieslab/jnose-core):

   ```bash
   git clone https://github.com/arieslab/jnose-core.git jnose-core
   ```

2. Install `jnose-core` into the local Maven repository:

   ```bash
   cd jnose-core
   mvn -q install
   cd ..
   ```

3. Build the executable adapter:

   ```bash
   cd jnose-adapter
   mvn -q package
   cd ..
   ```

4. Copy the adapter JAR into the shared workspace JAR directory:

   ```bash
   mkdir -p "$ME_WORKSPACE_DIRECTORY/jar"
   cp jnose-adapter/target/jnose-adapter-1.0.0.jar \
     "$ME_WORKSPACE_DIRECTORY/jar/jnose-adapter-1.0.0.jar"
   ```

After this step, `mhc test-smell --tool-name jnose` discovers the executable JAR from:

```text
WORKSPACE_DIRECTORY/jar/jnose-adapter-1.0.0.jar
```

## MHC test smell command

See the shared command reference for the full [`mhc test-smell`](../scripts/command.md#mhc-test-smell) option summary.

Generate method and callgraph data first, then run:

```bash
mhc test-smell \
  --workspace-directory "$ME_WORKSPACE_DIRECTORY" \
  --experiment-name "$ME_EXPERIMENT_NAME" \
  --jar-directory "$ME_WORKSPACE_DIRECTORY/jar" \
  --tool-name jnose \
  --stage all \
  --project "commons-io"
```

The workflow reads experiment data from:

```text
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/method/<project>.csv
WORKSPACE_DIRECTORY/experiment/EXPERIMENT_NAME/callgraph/<project>.csv
```

The workflow has two input modes:

- Callgraph mode: omit `--strategies`. MHC uses `method/` and `callgraph/` data, writes intermediates under `.test-smell/jnose/callgraph/`, and writes normalized output to `test-smell/jnose/callgraph/<project>.csv`.
- Strategy mode: pass one or more production-to-test mapping strategies with `--strategies`, such as `nc` or `omc--nc`. Each strategy reads from `t2p-link/<strategy>/`, writes intermediates under `.test-smell/jnose/<strategy>/`, and writes normalized output to `test-smell/jnose/<strategy>/<project>.csv`.
