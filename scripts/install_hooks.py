"""Install this worktree's hooks using the verified canonical installer."""
from pathlib import Path
from devtools_source import source


def main():
    """Pin the shared implementation before activating only the assigned hooks."""
    root=Path(__file__).resolve().parents[1]
    import importlib.util
    selected=source(root)
    spec=importlib.util.spec_from_file_location('egi_canonical_hook_installer',selected/'scripts/install_hooks.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.install(root)


if __name__=='__main__':
    main()
