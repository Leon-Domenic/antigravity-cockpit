import os
import sys
import tempfile
import shutil
import base64
import json
import io
import tarfile
import zipfile
from unittest.mock import MagicMock

# Mock dependencies
sys.modules['requests'] = MagicMock()
sys.modules['flask'] = MagicMock()
flask_mock = sys.modules['flask']

def mock_route(*args, **kwargs):
    def decorator(f):
        return f
    return decorator

app_instance = MagicMock()
app_instance.route = mock_route
flask_mock.Flask.return_value = app_instance
flask_mock.request = MagicMock()
flask_mock.Response = MagicMock()
flask_mock.jsonify = MagicMock(side_effect=lambda x: x)
flask_mock.send_file = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cockpit")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "agent")))

import cockpit_server
import agent_bridge

def run_tests():
    print("=== STARTING WORKSPACE END-TO-END SUITE ===")
    tmp_root = tempfile.mkdtemp(prefix="ws_test_")
    try:
        # Override Cockpit workspace dir
        cockpit_ws_dir = os.path.join(tmp_root, "cockpit_workspaces")
        os.makedirs(cockpit_ws_dir, exist_ok=True)
        cockpit_server.WORKSPACES_DIR = cockpit_ws_dir
        cockpit_server.WORKSPACES.clear()
        cockpit_server.get_current_user = lambda: {"username": "admin", "role": "admin", "tier": "enterprise", "max_workspaces": 999}

        # Override Agent workspace paths
        agent_home_ws = os.path.join(tmp_root, "agent_home_ws")
        agent_root_ws = os.path.join(tmp_root, "agent_root_ws")
        os.makedirs(agent_home_ws, exist_ok=True)
        os.makedirs(agent_root_ws, exist_ok=True)
        agent_bridge.AGENT_WORKSPACE_PATHS = [agent_home_ws, agent_root_ws]
        agent_bridge.get_primary_workspace = lambda: agent_home_ws

        # ----------------------------------------------------
        # 1. Test Project Tech Stack Detection
        # ----------------------------------------------------
        print("\n[TEST 1] Tech Stack Detection...")
        sample_react = os.path.join(tmp_root, "sample_react")
        os.makedirs(sample_react, exist_ok=True)
        with open(os.path.join(sample_react, "package.json"), "w") as f:
            json.dump({"dependencies": {"react": "^18.2.0", "vite": "^5.0.0"}}, f)
        assert cockpit_server.detect_tech_stack(sample_react) == "React", "Failed to detect React"

        sample_py = os.path.join(tmp_root, "sample_py")
        os.makedirs(sample_py, exist_ok=True)
        with open(os.path.join(sample_py, "requirements.txt"), "w") as f:
            f.write("flask>=3.0.0\nrequests\n")
        assert cockpit_server.detect_tech_stack(sample_py) == "Python", "Failed to detect Python"
        print("  -> Passed!")

        # ----------------------------------------------------
        # 2. Test Workspace Ingestion & Tree Generation
        # ----------------------------------------------------
        print("\n[TEST 2] Workspace Ingestion & Tree Generation...")
        ws_id = "ws_test_proj_01"
        ws_path = os.path.join(cockpit_ws_dir, ws_id)
        os.makedirs(ws_path, exist_ok=True)
        
        # Populate project
        with open(os.path.join(ws_path, "README.md"), "w", encoding="utf-8") as f:
            f.write("# My Awesome Project\nBuilt for Antigravity Cockpit agents!")
        src_path = os.path.join(ws_path, "src")
        os.makedirs(src_path, exist_ok=True)
        with open(os.path.join(src_path, "index.js"), "w", encoding="utf-8") as f:
            f.write("console.log('Hello from Cockpit Agent Workspace');")
        with open(os.path.join(ws_path, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "awesome-project", "version": "1.0.0", "dependencies": {"express": "^4.18.0"}}, f)

        stats = cockpit_server.scan_workspace_stats(ws_path)
        assert stats["file_count"] == 3
        assert stats["primary_language"] == "Express"
        
        tree = cockpit_server.build_workspace_tree(ws_path)
        assert len(tree) >= 2
        src_entry = next((e for e in tree if e["name"] == "src"), None)
        assert src_entry is not None and src_entry["is_dir"] is True
        assert len(src_entry["children"]) == 1
        assert src_entry["children"][0]["name"] == "index.js"
        print("  -> Passed!")

        # ----------------------------------------------------
        # 3. Test Cockpit to Agent Deploy Packaging
        # ----------------------------------------------------
        print("\n[TEST 3] Cockpit -> Agent Deploy Packaging & Extraction...")
        tar_bytes = cockpit_server.create_workspace_tar_gz(ws_path)
        b64_archive = base64.b64encode(tar_bytes).decode("utf-8")
        assert len(b64_archive) > 100

        # Simulate agent receiving the archive via /workspace/deploy
        agent_bridge.request.get_json = MagicMock(return_value={
            "archive": b64_archive,
            "workspace_name": "My Awesome Project",
            "workspace_id": ws_id,
            "clean_first": True
        })
        deploy_res = agent_bridge.deploy_workspace()
        assert deploy_res.get("success") is True, f"Deploy failed: {deploy_res}"
        # 3 project files + 1 .cockpit_workspace.json manifest = 4 files
        assert deploy_res.get("file_count") == 6, f"Expected 6 files, got {deploy_res.get('file_count')}"

        # Verify files in agent workspace
        assert os.path.exists(os.path.join(agent_home_ws, "README.md"))
        assert os.path.exists(os.path.join(agent_home_ws, "src", "index.js"))
        assert os.path.exists(os.path.join(agent_home_ws, ".cockpit_workspace.json"))
        
        with open(os.path.join(agent_home_ws, ".cockpit_workspace.json"), "r") as f:
            meta = json.load(f)
            assert meta["workspace_id"] == ws_id
            assert meta["workspace_name"] == "My Awesome Project"
        print("  -> Passed!")

        # ----------------------------------------------------
        # 4. Test Agent Status & Modifications
        # ----------------------------------------------------
        print("\n[TEST 4] Agent Workspace Status & Agent Modifications...")
        status_res = agent_bridge.workspace_status()
        assert status_res.get("active") is True
        assert status_res.get("workspace_id") == ws_id
        assert status_res.get("file_count") == 6

        # Simulate agent editing and generating a new file
        with open(os.path.join(agent_home_ws, "agent_output.txt"), "w") as f:
            f.write("Generated by AI Agent inside LXC container!")
        print("  -> Passed!")

        # ----------------------------------------------------
        # 5. Test Two-Way Sync (Agent Export -> Cockpit Pull)
        # ----------------------------------------------------
        print("\n[TEST 5] Two-Way Sync (Export from Agent, Pull into Cockpit)...")
        export_res = agent_bridge.export_workspace()
        assert export_res.get("success") is True
        b64_exported = export_res.get("archive")
        assert b64_exported is not None

        # Cockpit unpacks the export
        raw_pulled = base64.b64decode(b64_exported)
        with tarfile.open(fileobj=io.BytesIO(raw_pulled), mode="r:gz") as tf:
            tf.extractall(ws_path)

        assert os.path.exists(os.path.join(ws_path, "agent_output.txt")), "Agent output file failed to pull into Cockpit"
        with open(os.path.join(ws_path, "agent_output.txt"), "r") as f:
            assert "Generated by AI Agent" in f.read()

        updated_stats = cockpit_server.scan_workspace_stats(ws_path)
        # 3 initial files + .cockpit_workspace.json + agent_output.txt = 5 files
        assert updated_stats["file_count"] == 7, f"Expected 7 files, got {updated_stats['file_count']}"
        print("  -> Passed!")

        # ----------------------------------------------------
        # 6. Test ZIP Download Generation
        # ----------------------------------------------------
        print("\n[TEST 6] ZIP Archive Download Generation...")
        zip_bytes = cockpit_server.create_workspace_zip(ws_path)
        assert len(zip_bytes) > 200
        # Verify ZIP contains files
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            namelist = zf.namelist()
            assert "README.md" in namelist
            assert "src/index.js" in namelist or "src\\index.js" in namelist
            assert "agent_output.txt" in namelist
        print("  -> Passed!")

        # ----------------------------------------------------
        # 7. Test Workspace Cleaner
        # ----------------------------------------------------
        print("\n[TEST 7] Workspace Cleaner...")
        clean_res = agent_bridge.clean_workspace()
        assert clean_res.get("success") is True
        remaining = os.listdir(agent_home_ws)
        assert len(remaining) == 0, f"Expected 0 items, got {remaining}"
        print("  -> Passed!")

        # ----------------------------------------------------
        # 8. Test Git URL Normalization & Token Injection
        # ----------------------------------------------------
        print("\n[TEST 8] Git URL Normalization & Auth...")
        clone_url, safe_url, branch = cockpit_server.normalize_git_url("facebook/react")
        assert clone_url == "https://github.com/facebook/react.git"
        assert safe_url == "https://github.com/facebook/react.git"
        assert branch is None

        clone_url, safe_url, branch = cockpit_server.normalize_git_url("shadcn/ui@next")
        assert clone_url == "https://github.com/shadcn/ui.git"
        assert branch == "next"

        clone_url, safe_url, branch = cockpit_server.normalize_git_url("https://github.com/private/repo.git", token="ghp_mySecretToken123")
        assert "ghp_mySecretToken123@github.com" in clone_url
        assert "ghp_mySecretToken123" not in safe_url
        assert safe_url == "https://github.com/private/repo.git"
        print("  -> Passed!")

        # ----------------------------------------------------
        # 9. Test Local Git Clone & Git Pull (Cockpit)
        # ----------------------------------------------------
        print("\n[TEST 9] Local Git Clone & Git Pull (Cockpit Engine)...")
        git_remote_dir = os.path.join(tmp_root, "mock_remote_git")
        os.makedirs(git_remote_dir, exist_ok=True)
        import subprocess
        subprocess.run(["git", "init", "-b", "main", git_remote_dir], check=True, capture_output=True)
        subprocess.run(["git", "-C", git_remote_dir, "config", "user.name", "Tester"], check=True)
        subprocess.run(["git", "-C", git_remote_dir, "config", "user.email", "test@cockpit.dev"], check=True)

        with open(os.path.join(git_remote_dir, "app.py"), "w") as f:
            f.write("print('Hello from Git Repo')\n")
        with open(os.path.join(git_remote_dir, "package.json"), "w") as f:
            json.dump({"name": "git-app", "dependencies": {"next": "^14.0.0"}}, f)

        subprocess.run(["git", "-C", git_remote_dir, "add", "."], check=True)
        subprocess.run(["git", "-C", git_remote_dir, "commit", "-m", "Initial commit from remote"], check=True)

        # Mock request to git_clone_workspace
        flask_mock.request.get_json.return_value = {
            "repo_url": git_remote_dir,
            "branch": "main",
            "name": "cloned_git_project",
            "description": "Git clone test",
            "target_agent": "none"
        }
        clone_res = cockpit_server.git_clone_workspace()
        assert clone_res.get("success") is True, f"Clone failed: {clone_res}"
        ws_obj = clone_res.get("workspace")
        assert ws_obj["source"] == "git"
        assert ws_obj["git_branch"] == "main"
        assert len(ws_obj["git_commit"]) > 0
        assert "Initial commit" in ws_obj["git_commit_msg"]
        assert "Next.js" in ws_obj["primary_language"]
        cloned_ws_id = ws_obj["id"]

        # Now simulate a commit in the remote and test git_pull_workspace
        with open(os.path.join(git_remote_dir, "extra_feature.js"), "w") as f:
            f.write("// new feature added\n")
        subprocess.run(["git", "-C", git_remote_dir, "add", "."], check=True)
        subprocess.run(["git", "-C", git_remote_dir, "commit", "-m", "Add extra feature"], check=True)

        flask_mock.request.get_json.return_value = {"auto_redeploy": False}
        pull_res = cockpit_server.git_pull_workspace(cloned_ws_id)
        assert pull_res.get("success") is True, f"Pull failed: {pull_res}"
        updated_ws = pull_res.get("workspace")
        assert updated_ws["file_count"] == 3
        assert "Add extra feature" in updated_ws["git_commit_msg"]
        print("  -> Passed!")

        # ----------------------------------------------------
        # 10. Test Agent Bridge Direct Git Clone & Pull
        # ----------------------------------------------------
        print("\n[TEST 10] Agent Bridge Direct Git Clone & Git Pull...")
        flask_mock.request.get_json.return_value = {
            "repo_url": git_remote_dir,
            "branch": "main",
            "workspace_name": "agent_git_direct",
            "workspace_id": "ws_agent_git_1",
            "clean_first": True
        }
        agent_clone_res = agent_bridge.workspace_git_clone()
        assert agent_clone_res.get("success") is True, f"Agent git clone failed: {agent_clone_res}"
        assert os.path.exists(os.path.join(agent_home_ws, "app.py"))
        assert os.path.exists(os.path.join(agent_home_ws, ".cockpit_workspace.json"))

        agent_pull_res = agent_bridge.workspace_git_pull()
        assert agent_pull_res.get("success") is True, f"Agent git pull failed: {agent_pull_res}"
        print("  -> Passed!")

        print("\n>>> ALL 10 WORKSPACE SUITE TESTS PASSED PERFECTLY! <<<")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

if __name__ == "__main__":
    run_tests()
