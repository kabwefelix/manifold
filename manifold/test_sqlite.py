import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from manifold.self_development import _read_recent_sqlite_errors

print("Recent SQLite Errors:")
print(_read_recent_sqlite_errors(10))
