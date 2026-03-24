import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from manifold.hyperparameters import Hyperparameters
print(Hyperparameters.construct_system_prompt(0.5, "web"))
