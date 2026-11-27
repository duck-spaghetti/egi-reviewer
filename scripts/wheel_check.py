"""Build reproducibly and test the installed wheel away from the source checkout."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify():
    """Observe source/artifact agreement using the selected build backend, without IA."""
    import setuptools
    if setuptools.__version__ != "75.1.0":
        raise RuntimeError("Selected setuptools75.1.0 build prerequisite unavailable")
    scratch = ROOT / ".local"
    scratch.mkdir(exist_ok=True)
    environment = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                   "SOURCE_DATE_EPOCH": subprocess.check_output(
                       ["git", "-C", str(ROOT), "show", "-s", "--format=%ct", "HEAD"], text=True).strip()}
    with tempfile.TemporaryDirectory(prefix="wheel-fixture-", dir=scratch) as name:
        temporary = Path(name)
        with (scratch / "wheel-last.log").open("w") as log:
            def command(arguments, cwd=ROOT):
                """Run only explicit offline build/install/test arguments and retain their output."""
                subprocess.run([str(x) for x in arguments], cwd=cwd, env=environment,
                               stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)

            wheels = []
            for number in (1, 2):
                output = temporary / str(number)
                output.mkdir()
                command([sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation",
                         "--no-cache-dir", "--wheel-dir", output, ROOT])
                built = list(output.glob("*.whl"))
                if len(built) != 1:
                    raise RuntimeError("Expected one built artifact")
                wheels.append(built[0])
            if wheels[0].read_bytes() != wheels[1].read_bytes():
                raise RuntimeError("Repeated wheel builds differ")
            installed = temporary / "site"
            command([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile",
                     "--no-cache-dir", "--target", installed, wheels[0]])
            shutil.copytree(ROOT / "tests", temporary / "tests", ignore=shutil.ignore_patterns("__pycache__"))
            program = ("import sys,unittest;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
                       "import review;assert Path(review.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve());"
                       "suite=unittest.TestLoader().discover('tests',top_level_dir='.');"
                       "result=unittest.TextTestRunner(verbosity=2).run(suite);"
                       "sys.exit(0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1)")
            command([sys.executable, "-I", "-c", program, installed], cwd=temporary)
            digest = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
            retained = scratch / "artifacts"
            retained.mkdir(exist_ok=True)
            shutil.copyfile(wheels[0], retained / wheels[0].name)
            (scratch / "wheel-last.json").write_text(json.dumps(
                {"artifact": wheels[0].name, "sha256": digest, "identical_builds": 2,
                 "installed_tests": "passed", "source_date_epoch": environment["SOURCE_DATE_EPOCH"], "source": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()}, indent=2) + "\n")
            log.write("PASS installed artifact in isolated cwd; source checkout absent from import path\n")


if __name__ == "__main__":
    verify()
