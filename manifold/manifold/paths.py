import os

# Default to the directory above 'manifold/' package if MANIFOLD_HOME is not set
_DEFAULT_HOME = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFOLD_HOME = os.environ.get("MANIFOLD_HOME", _DEFAULT_HOME)

def get_path(filename: str) -> str:
    """Returns the absolute path for a given filename based on MANIFOLD_HOME."""
    return os.path.join(MANIFOLD_HOME, filename)
