"""Own Reviewer source/build/installed-artifact checks with shared pinned reporting."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys

from devtools_source import source


def main(argv=None):
    """Run selected package evidence and return blocked for unavailable pinned tooling."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("quick", "complete", "integration"), default="complete")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        source(root)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"schema_version": 1, "repository": "reviewer", "profile": args.profile,
                          "status": "blocked", "reason": "Pinned developer tools unavailable: " + type(error).__name__}))
        return 2
    from devchecks.report import Check, exit_code, report, run
    from devchecks.python_tests import check as python_check
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        checked = python_check(root, "integration")
    checked.name = "source-tests"
    checks = [checked]
    if args.profile != "quick":
        try:
            import setuptools
            import wheel
            available = setuptools.__version__ == "75.1.0"
        except ImportError:
            available = False
        if not available:
            checks.append(Check("wheel-prerequisite", "blocked", "Selected setuptools75.1.0/wheel build environment unavailable"))
        else:
            result = run("wheel-build-installed-tests", [sys.executable, root / "scripts/wheel_check.py"], root, timeout=600)
            if result.status == "passed":
                result.reason = "Identical repeated builds; isolated installed tests; .local/wheel-last.json and .local/wheel-last.log"
            checks.append(result)
    result = report("reviewer", args.profile, root, checks)
    print(json.dumps(result, indent=2) if args.json else f"reviewer {args.profile}: {result['status']}")
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
