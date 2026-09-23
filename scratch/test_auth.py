import requests

BASE_URL = "http://127.0.0.1:3000"

print("--- 1. Testing Unauthenticated Access ---")
r_status = requests.get(f"{BASE_URL}/api/status")
print(f"GET /api/status -> {r_status.status_code} (Expected 401)")
assert r_status.status_code == 401

r_agents = requests.get(f"{BASE_URL}/api/agents")
print(f"GET /api/agents -> {r_agents.status_code} (Expected 401)")
assert r_agents.status_code == 401

r_root = requests.get(f"{BASE_URL}/")
print(f"GET / -> {r_root.status_code} | Has 'MANDATORY ACCESS GATE': {'MANDATORY ACCESS GATE' in r_root.text}")
assert "MANDATORY ACCESS GATE" in r_root.text

print("\n--- 2. Testing Admin Login ---")
s_admin = requests.Session()
r_admin_login = s_admin.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "antigravity"})
print(f"POST /api/auth/login -> {r_admin_login.status_code}: {r_admin_login.text}")
assert r_admin_login.status_code == 200
data_admin = r_admin_login.json()
print("Admin tier:", data_admin.get("user", {}).get("tier"), "max_agents:", data_admin.get("user", {}).get("max_agents"))

r_admin_me = s_admin.get(f"{BASE_URL}/api/auth/me")
print(f"GET /api/auth/me (Admin) -> {r_admin_me.json()}")

r_admin_status = s_admin.get(f"{BASE_URL}/api/status")
print(f"GET /api/status with admin session -> {r_admin_status.status_code} (Expected 200)")
assert r_admin_status.status_code == 200

print("\n--- 3. Testing Signup with Starter Plan Quota (2 agents, 3 workspaces) ---")
s_starter = requests.Session()
uname = "starter_dev"
r_signup = s_starter.post(f"{BASE_URL}/api/auth/signup", json={
    "username": uname,
    "password": "password123",
    "name": "Starter Developer",
    "tier": "starter"
})
print(f"POST /api/auth/signup -> {r_signup.status_code}: {r_signup.text}")
assert r_signup.status_code in [200, 400]  # If already exists from prior test or new

if r_signup.status_code == 400:
    # Log in
    s_starter.post(f"{BASE_URL}/api/auth/login", json={"username": uname, "password": "password123"})

r_starter_me = s_starter.get(f"{BASE_URL}/api/auth/me")
me_data = r_starter_me.json()
print(f"GET /api/auth/me (Starter) -> {me_data}")
assert me_data["user"]["tier"] == "starter"
assert me_data["user"]["max_agents"] == 2
assert me_data["user"]["max_workspaces"] == 3

print("\n--- 4. Testing Quota Enforcement on Workspaces (max 3 for starter) ---")
# Create 3 template workspaces
for i in range(1, 4):
    r_ws = s_starter.post(f"{BASE_URL}/api/workspaces/create_template", json={
        "name": f"test_ws_{i}",
        "template": "blank"
    })
    print(f"Create workspace {i} -> {r_ws.status_code}")

# Attempt to create 4th workspace (exceeding quota of 3)
r_ws_fail = s_starter.post(f"{BASE_URL}/api/workspaces/create_template", json={
    "name": "test_ws_4_excess",
    "template": "blank"
})
print(f"Create workspace 4 (excess) -> {r_ws_fail.status_code}: {r_ws_fail.text}")
assert r_ws_fail.status_code == 403
assert "Workspace quota exceeded" in r_ws_fail.text

# Clean up test workspaces
for i in range(1, 4):
    # Find ws id
    all_ws = s_starter.get(f"{BASE_URL}/api/workspaces").json().get("workspaces", [])
    for w in all_ws:
        if w.get("name") == f"test_ws_{i}":
            s_starter.delete(f"{BASE_URL}/api/workspaces/{w['id']}")

print("\n--- ALL VERIFICATIONS PASSED SUCCESSFULLY! ---")
