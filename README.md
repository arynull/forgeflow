# forgeflow

A minimal, self-hosted CI/CD platform with YAML pipelines and local executors.
Standard library only, Python 3.10+.

## Install

```sh
pip install .
forge --version   # 0.1.0
```

Or run it straight from a checkout without installing:

```sh
python3 forge.py --version
```

## Pipeline format

forgeflow understands a small YAML subset: a `steps:` list where each step has a
`name` and a shell `run` command. Steps execute in order; the first failing step
stops the run.

```yaml
steps:
  - name: say hello
    run: echo hello
  - name: say bye
    run: echo bye
```

## Usage

Run a pipeline (recorded in `runs.json`):

```sh
forge run pipeline.yaml
# STEP-OK say hello
# STEP-OK say bye
```

Preview without executing:

```sh
forge run pipeline.yaml --dry
# WOULD-RUN say hello
# WOULD-RUN say bye
```

Inspect past runs:

```sh
forge runs list
forge runs show 1   # exits 2 if the id does not exist
```

## Develop

```sh
ruff check . && ruff format --check .
python3 -m py_compile forge.py
./tests_smoke.sh
```


## Trust model

Only run pipelines you wrote or trust — steps execute as your user\'s shell commands. Preview with `forge run PIPELINE.yaml --dry` first.

## License

MIT
