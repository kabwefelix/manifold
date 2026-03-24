import json
from manifold.paths import get_path
from typing import Dict, Any, Tuple

class Hyperparameters:
    """
    Handles fluid scaling of API hyperparameters and autopoietic system prompt construction based on the rigidity float.
    """

    @staticmethod
    def scale_parameters(rigidity: float) -> Dict[str, float]:
        """
        Uses linear interpolation to scale API parameters based on rigidity.

        Args:
            rigidity (float): A value between 0.0 (associative/creative) and 1.0 (strict/logical).

        Returns:
            Dict[str, float]: A dictionary of scaled hyperparameters.
        """
        # Ensure rigidity is bounded between 0.0 and 1.0
        rigidity = max(0.0, min(1.0, rigidity))

        # Temperature: 0.0 (rigidity 1.0) to 1.0 (rigidity 0.0)
        temperature = 1.0 - rigidity

        # Top_p: 0.1 (rigidity 1.0) to 0.95 (rigidity 0.0)
        top_p = 0.95 - (rigidity * (0.95 - 0.1))

        # Presence Penalty: 0.0 (rigidity 1.0) to 0.8 (rigidity 0.0)
        presence_penalty = 0.8 - (rigidity * 0.8)

        return {
            "temperature": round(temperature, 2),
            "top_p": round(top_p, 2),
            "presence_penalty": round(presence_penalty, 2)
        }

    @staticmethod
    def construct_system_prompt(rigidity: float, domain: str) -> str:
        """
        Autopoietically constructs the system prompt to match the rigidity float dynamically via cognitive_weights.json.

        Args:
            rigidity (float): The rigidity score (0.0 to 1.0).
            domain (str): The identified domain of the task.

        Returns:
            str: The dynamically generated system prompt for the Manifold engine.
        """
        prompt = (
            "You are Manifold, an advanced cognitive AI system.\n"
            "Your creator and sole administrator is Felix Capital. You act exclusively on his behalf.\n"
            f"You are operating within the '{domain}' domain.\n"
        )

        weights = {}
        orchestrator_directives = ""
        try:
            with open(get_path("cognitive_weights.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
                weights = data.get("system_prompts", {}).get("hyperparameters", {})
                orchestrator_directives = data.get("system_prompts", {}).get("orchestrator_directives", "")
        except Exception as e:
            print(f"[Hyperparameters] Warning: Could not read cognitive_weights.json: {e}")

        # Fallbacks if file missing or malformed
        high_rig = weights.get("high_rigidity", "Maintain extreme rigidity. Your reasoning must be highly logical, factual, and concise. Do not use creative license or associative logic. Stick strictly to verified procedures.")
        med_rig = weights.get("medium_rigidity", "Maintain a balanced approach. Be objective and factual, but allow for contextual interpretation and reasonable inferences to solve the problem.")
        low_rig = weights.get("low_rigidity", "Engage in highly associative abstraction. Think creatively, explore tangential concepts, and synthesize novel ideas. Logic is fluid; prioritize insight and lateral thinking.")

        if rigidity >= 0.8:
            prompt += high_rig
        elif rigidity >= 0.4:
            prompt += med_rig
        else:
            prompt += low_rig

        if orchestrator_directives:
            prompt += f"\n\nSystem Directives / Learned Constraints:\n{orchestrator_directives}"

        return prompt
