"""Verify the pinned development-tool source before importing any shared code."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def source(root):
    """Resolve an explicit tool checkout and verify each imported file against Git."""
    policy=json.loads((root/'.checks/tool-source.json').read_text())
    revision=policy['revision']
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',revision):
        raise ValueError('Tool revision must be an exact commit SHA')
    selected=Path(os.environ.get('EGI_DEVTOOLS_SOURCE',str(root/policy['source']))).resolve()
    for name in ('scripts/devchecks/__init__.py','scripts/devchecks/report.py',
                 'scripts/devchecks/commit_titles.py','scripts/devchecks/python_tests.py',
                 'scripts/commit_guard.py','scripts/install_hooks.py'):
        expected=subprocess.check_output(['git','-C',str(selected),'show',revision+':'+name],stderr=subprocess.DEVNULL)
        if (selected/name).read_bytes()!=expected:
            raise ValueError('Pinned development-tool source mismatch: '+name)
    sys.path.insert(0,str(selected/'scripts'))
    return selected
