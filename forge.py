"""forgeflow - a minimal self-hosted CI/CD runner.

Parses a small YAML pipeline subset (a list of steps, each with a name and a
shell ``run`` command), executes the steps in order, and records past runs in a
local ``runs.json`` file. Standard library only, Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

__version__ = "0.1.0"

RUNS_FILE = Path("runs.json")


class PipelineError(Exception):
    """Raised when a pipeline file cannot be parsed."""


def _unquote(value: str) -> str:
    """Strip matching single or double quotes from a scalar value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_pipeline(path: str | Path) -> list[dict[str, str]]:
    """Parse a minimal YAML pipeline into a list of ``{name, run}`` steps.

    Supported subset::

        steps:
          - name: say hello
            run: echo hello
          - name: say bye
            run: echo bye
    """
    text = Path(path).read_text(encoding="utf-8")
    steps: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_steps = False

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[0].isspace():
            key = raw.strip().rstrip(":")
            in_steps = key == "steps" and raw.strip().endswith(":")
            current = None
            continue
        if not in_steps:
            continue

        content = raw.strip()
        if content.startswith("-"):
            content = content[1:].strip()
            current = {}
            steps.append(current)
        if not content:
            continue
        if ":" not in content:
            raise PipelineError(f"invalid step line: {raw.strip()!r}")

        key, _, value = content.partition(":")
        key = key.strip()
        value = _unquote(value.strip())
        if current is None:
            current = {}
            steps.append(current)
        current[key] = value

    if not steps:
        raise PipelineError("pipeline has no steps")

    for index, step in enumerate(steps, start=1):
        if not step.get("name"):
            raise PipelineError(f"step {index} is missing a name")
        if not step.get("run"):
            raise PipelineError(f"step {index} is missing a run command")
    return steps


def load_runs(path: Path = RUNS_FILE) -> list[dict]:
    """Return recorded runs, or an empty list if the file is absent."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    runs = data.get("runs", []) if isinstance(data, dict) else []
    return runs if isinstance(runs, list) else []


def save_runs(runs: list[dict], path: Path = RUNS_FILE) -> None:
    path.write_text(json.dumps({"runs": runs}, indent=2) + "\n", encoding="utf-8")


def _next_id(runs: list[dict]) -> str:
    highest = 0
    for run in runs:
        try:
            highest = max(highest, int(run.get("id", 0)))
        except (TypeError, ValueError):
            continue
    return str(highest + 1)


def cmd_run(args: argparse.Namespace) -> int:
    try:
        steps = parse_pipeline(args.pipeline)
    except (PipelineError, OSError) as exc:
        print(f"forge: error: {exc}", file=sys.stderr)
        return 1

    if args.dry:
        for step in steps:
            print(f"WOULD-RUN {step['name']}")
        return 0

    started = time.time()
    results: list[dict[str, str]] = []
    exit_code = 0
    for step in steps:
        completed = subprocess.run(step["run"], shell=True, check=False)
        if completed.returncode != 0:
            print(f"STEP-FAIL {step['name']}", file=sys.stderr)
            results.append({"name": step["name"], "status": "failed"})
            exit_code = completed.returncode or 1
            break
        print(f"STEP-OK {step['name']}")
        results.append({"name": step["name"], "status": "ok"})

    runs = load_runs()
    runs.append(
        {
            "id": _next_id(runs),
            "pipeline": str(args.pipeline),
            "status": "ok" if exit_code == 0 else "failed",
            "started": started,
            "finished": time.time(),
            "steps": results,
        }
    )
    save_runs(runs)
    return exit_code


def cmd_runs_list(args: argparse.Namespace) -> int:
    runs = load_runs()
    if not runs:
        print("no runs recorded")
        return 0
    print(f"{'ID':<6}{'STATUS':<9}{'STEPS':<7}PIPELINE")
    for run in runs:
        steps = run.get("steps", [])
        print(
            f"{str(run.get('id', '?')):<6}"
            f"{str(run.get('status', '?')):<9}"
            f"{len(steps):<7}"
            f"{run.get('pipeline', '?')}"
        )
    return 0


def cmd_runs_show(args: argparse.Namespace) -> int:
    runs = load_runs()
    for run in runs:
        if str(run.get("id")) == str(args.run_id):
            print(f"run {run.get('id')}")
            print(f"pipeline: {run.get('pipeline', '?')}")
            print(f"status: {run.get('status', '?')}")
            for step in run.get("steps", []):
                print(f"  {step.get('status', '?'):<7}{step.get('name', '?')}")
            return 0
    print(f"forge: error: no run with id {args.run_id}", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge", description="Minimal CI/CD runner.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run a pipeline file")
    run_parser.add_argument("pipeline", help="path to PIPELINE.yaml")
    run_parser.add_argument(
        "--dry", action="store_true", help="print steps without executing them"
    )
    run_parser.set_defaults(func=cmd_run)

    runs_parser = sub.add_parser("runs", help="inspect past runs")
    runs_sub = runs_parser.add_subparsers(dest="runs_command", required=True)
    list_parser = runs_sub.add_parser("list", help="list past runs")
    list_parser.set_defaults(func=cmd_runs_list)
    show_parser = runs_sub.add_parser("show", help="show a single run by id")
    show_parser.add_argument("run_id", help="run id to show")
    show_parser.set_defaults(func=cmd_runs_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
