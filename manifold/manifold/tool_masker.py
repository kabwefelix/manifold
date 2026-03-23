import os
from typing import List, Dict, Any

class ToolMasker:
    """
    Handles dynamically loading and filtering OpenClaw skills based on the identified domain.
    It scans the `/skills` directory for `SKILL.md` files.

    Attributes:
        skills_dir (str): The directory containing the skill subdirectories.
    """

    def __init__(self, skills_dir: str = None):
        """
        Initializes the ToolMasker.

        Args:
            skills_dir (str): The relative path to the directory containing skills.
        """
        self.skills_dir = skills_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")

    def reload(self):
        """
        Forces a reload of the tool cache if one was implemented.
        Currently, since get_masked_tools rescans the directory on every call,
        this method serves as a semantic trigger for hot-reloading.
        """
        print(f"[ToolMasker] Reloading tools from '{self.skills_dir}'...")

    def get_masked_tools(self, target_domain: str) -> List[Dict[str, Any]]:
        """
        Scans the skills directory for SKILL.md files, parses their metadata,
        and filters them based on the target domain. Returns tool schemas.

        Args:
            target_domain (str): The domain identified by the VectorObserver (e.g., 'math').

        Returns:
            List[Dict[str, Any]]: A list of tool schema dictionaries.
        """
        masked_tools = []

        if not os.path.isdir(self.skills_dir):
            print(f"[ToolMasker] Warning: Skills directory '{self.skills_dir}' not found.")
            return masked_tools

        for item in os.listdir(self.skills_dir):
            item_path = os.path.join(self.skills_dir, item)

            # Check if it's a directory containing a SKILL.md
            if os.path.isdir(item_path):
                skill_md_path = os.path.join(item_path, "SKILL.md")
                if os.path.exists(skill_md_path):
                    metadata = self._parse_metadata_from_md(skill_md_path)
                    skill_domain = metadata.get("domain", "general").lower()

                    if skill_domain == target_domain or skill_domain == "general":
                        name = metadata.get("name", item)
                        description = metadata.get("description", f"A tool for {name}")

                        tool_schema = {
                            "type": "function",
                            "function": {
                                "name": name,
                                "description": description,
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "input_data": {
                                            "type": "string",
                                            "description": "The input to the tool."
                                        }
                                    },
                                    "required": ["input_data"]
                                }
                            }
                        }
                        masked_tools.append(tool_schema)

        return masked_tools

    def _parse_metadata_from_md(self, filepath: str) -> Dict[str, str]:
        """
        Reads a SKILL.md file and extracts all metadata from the YAML frontmatter.
        """
        metadata = {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                in_yaml = False
                for line in lines:
                    line = line.strip()
                    if line == "---":
                        if not in_yaml:
                            in_yaml = True
                            continue
                        else:
                            break # End of frontmatter
                    if in_yaml and ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip().lower()] = value.strip()
        except Exception as e:
            print(f"[ToolMasker] Error reading {filepath}: {e}")

        return metadata
