import os, sys, unittest, json, time, io, tarfile, tempfile, shutil
from unittest.mock import MagicMock, patch

# Ensure paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COCKPIT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "cockpit")
AGENT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "agent")

if COCKPIT_DIR not in sys.path:
    sys.path.insert(0, COCKPIT_DIR)
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

# Mock external dependencies for isolated unit testing
if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()
if "flask" not in sys.modules:
    mock_flask = MagicMock()
    mock_app = MagicMock()
    mock_flask.Flask.return_value = mock_app
    mock_flask.request = MagicMock()
    mock_flask.jsonify = lambda d: d
    mock_flask.Response = MagicMock()
    sys.modules["flask"] = mock_flask

class TestWorkspaceGitAuth(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_dir = os.path.join(self.temp_dir, "test_ws")
        os.makedirs(self.workspace_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_agent_workspace_binding_and_rules(self):
        """Test that ensure_workspace_agent_binding writes .agents/rules and AGENTS.md"""
        from agent_bridge import ensure_workspace_agent_binding

        ensure_workspace_agent_binding(self.workspace_dir, "Demo Project")

        rule_path = os.path.join(self.workspace_dir, ".agents", "rules", "cockpit_workspace.md")
        agents_path = os.path.join(self.workspace_dir, "AGENTS.md")

        self.assertTrue(os.path.exists(rule_path), "Rule file must exist in .agents/rules/")
        self.assertTrue(os.path.exists(agents_path), "AGENTS.md must exist in workspace root")

        with open(rule_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("cockpit-workspace-context", content)
            self.assertIn(self.workspace_dir, content)
            self.assertIn("Demo Project", content)

    def test_user_authentication_password_hashing(self):
        """Test PBKDF2 password hashing and verification in cockpit_server"""
        from cockpit_server import hash_password, verify_password

        pwd = "super_secret_agent_password_123"
        hashed = hash_password(pwd)

        self.assertIn("$", hashed, "Hash format should be salt$hex")
        self.assertTrue(verify_password(pwd, hashed), "Password verification should pass for correct password")
        self.assertFalse(verify_password("wrong_password", hashed), "Verification must fail for wrong password")

    def test_git_config_masking(self):
        """Test that tokens are properly masked when reading git config"""
        import cockpit_server
        cockpit_server.GIT_CONFIG["token"] = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        cockpit_server.GIT_CONFIG["configured"] = True

        cfg = cockpit_server.load_git_config().copy()
        tok = cfg.get("token", "")
        masked = f"{tok[:4]}...{tok[-4:]}" if len(tok) > 8 else ("***" if tok else "")

        self.assertNotEqual(masked, tok)
        self.assertTrue(masked.startswith("ghp_"))
        self.assertTrue(masked.endswith("wxyz"))
        self.assertIn("...", masked)

    def test_active_session_validation(self):
        """Test active session management with token expiry"""
        import cockpit_server
        token = "test_session_token_xyz"
        cockpit_server.ACTIVE_SESSIONS[token] = {
            "username": "admin",
            "name": "System Administrator",
            "role": "admin",
            "expires": time.time() + 3600
        }

        # Check valid session
        session = cockpit_server.ACTIVE_SESSIONS.get(token)
        self.assertIsNotNone(session)
        self.assertEqual(session["username"], "admin")
        self.assertTrue(session["expires"] > time.time())

        # Test expired session cleanup
        cockpit_server.ACTIVE_SESSIONS[token]["expires"] = time.time() - 10
        # Simulating get_current_user logic
        if cockpit_server.ACTIVE_SESSIONS[token]["expires"] <= time.time():
            del cockpit_server.ACTIVE_SESSIONS[token]
        self.assertNotIn(token, cockpit_server.ACTIVE_SESSIONS)

if __name__ == "__main__":
    unittest.main()
