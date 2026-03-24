from manifold.local_tools import execute_builtin_tool

print("--- TESTING UNAUTHORIZED (NO PASSWORD) ---")
res1 = execute_builtin_tool("run_command", {"command": "echo hello"})
print(res1)

print("\n--- TESTING UNAUTHORIZED (WRONG PASSWORD) ---")
res2 = execute_builtin_tool("run_command", {"command": "echo hello", "admin_password": "password123"})
print(res2)

print("\n--- TESTING AUTHORIZED (CORRECT PASSWORD) ---")
res3 = execute_builtin_tool("run_command", {"command": "echo hello", "admin_password": "2020Felix"})
print(res3)
