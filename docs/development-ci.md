# Required package verification — EGI-139

The PR-to-dev workflow invokes the existing owning Complete command and the
canonical commit-object validator. Official GitHub actions are pinned to exact
SHAs. Canonical app source is selected by `.checks/tool-source.json` and verified
before import; inherited Git-hook variables cannot redirect that source lookup.

The selected Python3.13 runner installs the existing setuptools75.1.0 and wheel0.43.0
build tools, then performs the same offline repeated wheel builds, byte comparison,
isolated install and installed-package tests as local checks. No model/provider key,
extraction-feature change or paid request is introduced. The wheel receipt identifies
the actual source/hash; it is preserved with build/test logs and the wheel artifact.

The required check identity is **EGI / reviewer**. Actual failed/passed remote runs
and effective required-check readback are necessary before claiming enforcement.
Scoped draft validation PRs remain separate from final delivery. No protected-branch
merge, release or deployment is authorized by this setup.

See [GitHub status checks](https://docs.github.com/en/pull-requests/reference/status-checks)
and the current workspace execution record for observed enforcement evidence.
