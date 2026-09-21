import sys
import os
import shutil
import tempfile
import json

from unittest.mock import MagicMock
sys.modules['requests'] = MagicMock()
sys.modules['flask'] = MagicMock()
flask_mock = sys.modules['flask']
flask_mock.Flask.return_value = MagicMock()
flask_mock.request = MagicMock()
flask_mock.Response = MagicMock()
flask_mock.jsonify = MagicMock(side_effect=lambda x: x)
flask_mock.send_file = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cockpit")))
import cockpit_server

print("Testing cockpit_server helper functions...")

# Create a temporary workspace folder to test
tmp_dir = tempfile.mkdtemp()
try:
    test_ws = os.path.join(tmp_dir, "test-ws")
    os.makedirs(test_ws, exist_ok=True)
    
    # Create sample files
    with open(os.path.join(test_ws, "package.json"), "w") as f:
        f.write(json.dumps({"name": "my-test-app", "dependencies": {"react": "^18.0.0"}}))
        
    with open(os.path.join(test_ws, "README.md"), "w") as f:
        f.write("# My Test App\nWelcome!")

    src_dir = os.path.join(test_ws, "src")
    os.makedirs(src_dir, exist_ok=True)
    with open(os.path.join(src_dir, "App.tsx"), "w") as f:
        f.write("export default function App() { return <h1>Hello</h1>; }")

    # 1. Test tech stack detection
    detected = cockpit_server.detect_tech_stack(test_ws)
    print("Detected stack:", detected)
    assert "react" in detected.lower() or "typescript" in detected.lower() or "node" in detected.lower(), f"Unexpected stack: {detected}"

    # 2. Test workspace stats scan
    stats = cockpit_server.scan_workspace_stats(test_ws)
    print("Scanned stats:", stats)
    assert stats["file_count"] >= 3, f"File count was {stats['file_count']}"
    assert stats["dir_count"] >= 1, f"Dir count was {stats['dir_count']}"
    assert stats["size_bytes"] > 0, f"Size was {stats['size_bytes']}"

    # 3. Test workspace tree build
    tree = cockpit_server.build_workspace_tree(test_ws)
    print(f"Built tree items: {len(tree)}")
    assert isinstance(tree, list), f"Expected list, got {type(tree)}"
    assert len(tree) >= 2, f"Expected at least 2 entries, got {len(tree)}"
    src_entry = next((e for e in tree if e["name"] == "src"), None)
    assert src_entry is not None, "src directory missing from tree"
    assert src_entry["is_dir"] is True
    assert len(src_entry["children"]) >= 1
    assert src_entry["children"][0]["name"] == "App.tsx"

    # 4. Test tar.gz archive creation
    tar_bytes = cockpit_server.create_workspace_tar_gz(test_ws)
    print(f"Generated tar.gz bytes length: {len(tar_bytes)}")
    assert isinstance(tar_bytes, bytes)
    assert len(tar_bytes) > 50

    # 5. Test zip creation
    zip_bytes = cockpit_server.create_workspace_zip(test_ws)
    print(f"Generated zip bytes length: {len(zip_bytes)}")
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 50

    print("ALL WORKSPACE UNIT TESTS PASSED!")
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)
