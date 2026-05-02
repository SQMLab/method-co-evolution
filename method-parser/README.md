# method-parser

Java 21 / Maven module that extracts methods and call graphs from Java source using JavaParser. Produces CSV datasets consumed by the `mhc` CLI.

## Build

```bash
cd method-parser
mvn clean install -DskipTests
```

The fat JAR is written to `target/method-parser-*.jar`. The helper script builds and copies it to the cache in one step:

```bash
scripts/build_mp.sh   # copies JAR to <ME_CACHE_DIRECTORY>/jar/
```

The `mhc scan-method` and `mhc call-graph` commands resolve the JAR from `--jar-directory` at runtime.

## Datasets

### `data/method/{project}.csv` — method index

One row per method or constructor extracted from the repository at the indexed commit.

| Column | Type | Description |
|--------|------|-------------|
| `project` | string | Repository name |
| `name` | string | Simple method or constructor name |
| `url` | string | GitHub blob URL (file + line anchor) |
| `artifact` | string | `test` or `production` |
| `start_line` | int | First line of the method body |
| `end_line` | int | Last line of the method body |
| `expression` | string | `method` or `constructor` |
| `pkg` | string | Java package name |
| `fqn` | string | Fully-qualified name (`Class#method`) |
| `fqs` | string | Fully-qualified signature (with parameter types) |
| `fqs_alt` | string | Alternative FQS using simple type names |
| `testlinker_fqs` | string | FQS in TestLinker format |
| `testlinker_fqp` | string | FQP (fully-qualified path) in TestLinker format |
| `file` | string | Relative path to the Java source file |
| `abstract` | int | `1` if the method is abstract, else `0` |
| `parser` | string | Always `javaparser` |
| `resolver` | string | Symbol resolver strategy used |
| `hash` | string | Git commit hash the index was built from |

The `url` column is the primary key used throughout the pipeline to identify methods.

### `data/call-graph/{project}.csv` — fan-out (test → production calls)

One row per directed call edge. `fan-out` files record what a method calls; `fan-in` files record what calls a method. Both share the same schema.

| Column | Type | Description |
|--------|------|-------------|
| `project` | string | Repository name |
| `from_name` / `to_name` | string | Simple method name |
| `from_url` / `to_url` | string | GitHub blob URL of the method |
| `from_expression` / `to_expression` | string | `method` or `constructor` |
| `from_pkg` / `to_pkg` | string | Java package |
| `from_fqn` / `to_fqn` | string | Fully-qualified name |
| `from_fqs` / `to_fqs` | string | Fully-qualified signature |
| `from_fqs_alt` / `to_fqs_alt` | string | Alternative FQS |
| `from_testlinker_fqs` / `to_testlinker_fqs` | string | TestLinker FQS |
| `from_testlinker_fqp` / `to_testlinker_fqp` | string | TestLinker FQP |
| `from_start` / `from_end` | int | Line range of the `from` method |
| `to_start` / `to_end` | int | Line range of the `to` method |
| `from_invocation` | int | Line where the call appears in the `from` method (fan-out only) |
| `from_lcba` / `to_lcba` | int | Last call before an assertion (line number) |
| `from_file` / `to_file` | string | Relative source file path |
| `from_caller_url` / `to_caller_url` | string | Caller URL (populated for deep call chains) |
| `from_call_depth` / `to_call_depth` | int | Depth in the call chain |
| `hash` | string | Git commit hash |
| `from_resolver` / `to_resolver` | string | Symbol resolver strategy |

Fan-out files are stored under `data/fan-out/` after link generation. Fan-in files are stored under `data/fan-in/`.
