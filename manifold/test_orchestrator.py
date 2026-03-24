import asyncio
import os
import sys

# Ensure manifold is in path
sys.path.insert(0, os.path.dirname(__file__))

from manifold.orchestrator import Orchestrator

async def main():
    o = Orchestrator()
    print("Testing 'What is the current date and time?' (requires run_command or equivalent tool)")
    resp = await o.run("What is the current date and time on this Windows machine? Use run_command.", "system", 0.5, 1)
    print("\n--- Final Response ---")
    print(resp)

if __name__ == "__main__":
    asyncio.run(main())
