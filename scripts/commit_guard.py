"""Forward hooks and CI to the verified canonical title validator, without a fork."""
from pathlib import Path
import subprocess
import sys
from devtools_source import source


def main():
    """Validate source integrity before forwarding the original hook stdin/arguments."""
    root=Path(__file__).resolve().parents[1]
    try:
        selected=source(root)
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        print('Pinned developer tools unavailable: '+type(error).__name__,file=sys.stderr)
        return 2
    return subprocess.run([sys.executable,selected/'scripts/commit_guard.py','--root',root,*sys.argv[1:]],check=False).returncode


if __name__=='__main__':
    raise SystemExit(main())
