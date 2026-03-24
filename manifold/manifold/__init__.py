import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_HOME = PACKAGE_DIR.parent
REPO_ROOT = DEFAULT_HOME.parent
_PLACEHOLDER_MANIFOLD_HOME = "/absolute/path/to/manifold/data"


def _manual_load_dotenv(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]

        os.environ[key] = value


def bootstrap_environment() -> Path:
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file, override=True)
        except Exception:
            _manual_load_dotenv(env_file)

    configured_home = os.environ.get("MANIFOLD_HOME", "").strip()
    if not configured_home or configured_home == _PLACEHOLDER_MANIFOLD_HOME:
        resolved_home = DEFAULT_HOME
    else:
        candidate = Path(configured_home).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        resolved_home = candidate.resolve()

    resolved_home.mkdir(parents=True, exist_ok=True)
    os.environ["MANIFOLD_HOME"] = str(resolved_home)
    return resolved_home


MANIFOLD_HOME = bootstrap_environment()
