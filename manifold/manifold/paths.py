from pathlib import Path

from manifold import MANIFOLD_HOME as _MANIFOLD_HOME
from manifold import PACKAGE_DIR as _PACKAGE_DIR
from manifold import REPO_ROOT as _REPO_ROOT

MANIFOLD_HOME = Path(_MANIFOLD_HOME)
PACKAGE_DIR = Path(_PACKAGE_DIR)
REPO_ROOT = Path(_REPO_ROOT)


def get_path(filename: str) -> str:
    """Return an absolute path inside MANIFOLD_HOME."""
    return str(MANIFOLD_HOME / filename)


def get_package_path(filename: str) -> str:
    """Return an absolute path inside the installed package directory."""
    return str(PACKAGE_DIR / filename)


def get_repo_path(filename: str) -> str:
    """Return an absolute path inside the repository root."""
    return str(REPO_ROOT / filename)
