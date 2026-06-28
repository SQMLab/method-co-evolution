# Replication Package

This document describes how to use the Zenodo replication package to replay the method co-evolution experiments. The package is organized so that its `workspace/...` files can be copied directly into the cloned project.

## 1. Get the Project and Package

Clone the GitHub project from https://anonymous.4open.science/r/test-evolution. For project setup, dependencies, and build instructions, read the project README:

```text
README.md
```

Download the replication package from Zenodo:

```text
https://zenodo.org/records/0000000
```

The Zenodo URL is a placeholder and should be replaced with the final record URL before publication.

## 2. Prepare the Workspace

Extract the Zenodo archive. It should contain a packaged `.env` file and a `workspace/` directory whose internal paths are preserved.

Copy the packaged `.env` into the cloned project root:

```bash
cp /path/to/replication-package/.env /path/to/method-co-evolution/.env
```

Copy the packaged `workspace/` directory into the cloned project root:

```bash
cp -R /path/to/replication-package/workspace /path/to/method-co-evolution/
```

After copying, the cloned project should contain paths such as:

```text
workspace/experiment/main/project.csv
workspace/experiment/main/method/
workspace/experiment/main/method-history/
```

## 3. Configure `.env`

Set `PROJECT_DIRECTORY` to the local path of the cloned project. Keep
## 4. Package Contents

The package contains raw input data and selected shareable derived inputs needed to replay the experiment notebooks. Method-history CSV files are included. Method-history JSON files and compressed archives are excluded.

Main experiment contents:

```text
workspace/experiment/main/callgraph
workspace/experiment/main/class
workspace/experiment/main/method
workspace/experiment/main/method-code
workspace/experiment/main/method-history
workspace/experiment/main/project.csv
workspace/experiment/main/t2p-link/nc
workspace/experiment/main/t2p-link/omc
workspace/experiment/main/t2p-link/omc--nc
workspace/experiment/main/t2p-tech
workspace/experiment/main/test-smell/jnose/omc--nc
```


Evaluation experiment contents are included for `tctracer-2020`, `tctracer-2022`, `testlinker`, and `t2plinker`. Each experiment contains:

```text
workspace/experiment/<experiment>/callgraph
workspace/experiment/<experiment>/class
workspace/experiment/<experiment>/method
workspace/experiment/<experiment>/method-code
workspace/experiment/<experiment>/project.csv
workspace/experiment/<experiment>/t2p-link/combined
workspace/experiment/<experiment>/t2p-link/lc
workspace/experiment/<experiment>/t2p-link/lcba
workspace/experiment/<experiment>/t2p-link/lcs-b
workspace/experiment/<experiment>/t2p-link/lcs-u
workspace/experiment/<experiment>/t2p-link/leven
workspace/experiment/<experiment>/t2p-link/nc
workspace/experiment/<experiment>/t2p-link/ncc
workspace/experiment/<experiment>/t2p-link/omc
workspace/experiment/<experiment>/t2p-link/omc--nc
workspace/experiment/<experiment>/t2p-link/tarantula
workspace/experiment/<experiment>/t2p-link/testlinkerv2
workspace/experiment/<experiment>/t2p-link/tfidf
workspace/experiment/<experiment>/t2p-tech
workspace/experiment/<experiment>/testlinker/output/codet5/testlinkerv2
```


## 5. Replay the Experiments

Complete the project setup described in the README before running the notebooks. Then run the notebooks in this order from the cloned project:

```text
co-evolution/src/ptc/run/method_link_run.ipynb
co-evolution/src/ptc/run/method_history_run.ipynb
co-evolution/src/ptc/run/method_linker_evaluation.ipynb
co-evolution/src/ptc/run/rq_plot_run.ipynb
```
