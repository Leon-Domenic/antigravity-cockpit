import unittest
import os
import sys

# Add cockpit directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COCKPIT_DIR = os.path.join(BASE_DIR, "cockpit")
if COCKPIT_DIR not in sys.path:
    sys.path.insert(0, COCKPIT_DIR)

class TestInstallerAndEngineSpecs(unittest.TestCase):

    def test_installer_files_exist(self):
        installers = [
            os.path.join(BASE_DIR, "agent", "install.sh"),
            os.path.join(BASE_DIR, "agent", "installers", "common.sh"),
            os.path.join(BASE_DIR, "agent", "installers", "install_antigravity.sh"),
            os.path.join(BASE_DIR, "agent", "installers", "install_codex.sh"),
            os.path.join(BASE_DIR, "agent", "installers", "install_hermes.sh"),
            os.path.join(BASE_DIR, "agent", "installers", "install_openclaw.sh"),
            os.path.join(BASE_DIR, "agent", "installers", "install_ceo.sh"),
            os.path.join(BASE_DIR, "scripts", "pve_provision_agent.sh"),
        ]
        for f in installers:
            self.assertTrue(os.path.isfile(f), f"Missing installer file: {f}")

    def test_installer_scripts_syntax_and_keywords(self):
        # Hermes must check for KVM virtualization
        hermes_file = os.path.join(BASE_DIR, "agent", "installers", "install_hermes.sh")
        with open(hermes_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("check_system_resources", content)
            self.assertIn('"kvm"', content)
            self.assertIn("ollama", content)
            self.assertIn("docker", content)

        # OpenClaw must check for KVM virtualization
        openclaw_file = os.path.join(BASE_DIR, "agent", "installers", "install_openclaw.sh")
        with open(openclaw_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("check_system_resources", content)
            self.assertIn('"kvm"', content)
            self.assertIn("playwright", content)
            self.assertIn("chromium", content)

        # Master install.sh must support --engine parsing
        master_file = os.path.join(BASE_DIR, "agent", "install.sh")
        with open(master_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("--engine", content)
            self.assertIn("antigravity", content)
            self.assertIn("codex", content)
            self.assertIn("hermes", content)
            self.assertIn("openclaw", content)
            self.assertIn("ceo", content)

        # Proxmox provisioner must support both qm create (VM) and pct create (LXC)
        pve_file = os.path.join(BASE_DIR, "scripts", "pve_provision_agent.sh")
        with open(pve_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("qm create", content)
            self.assertIn("pct create", content)
            self.assertIn("cloud-init", content)

    def test_default_agents_and_virt_type(self):
        from unittest.mock import MagicMock
        if "requests" not in sys.modules:
            sys.modules["requests"] = MagicMock()
        if "flask" not in sys.modules:
            sys.modules["flask"] = MagicMock()
            
        from cockpit_server import DEFAULT_AGENTS, get_agent_vm_type

        # Check default agents have vm_type set
        for agent in DEFAULT_AGENTS:
            self.assertIn("vm_type", agent, f"Agent {agent['id']} missing vm_type")
            if agent["type"] in ["hermes", "openclaw"]:
                self.assertEqual(agent["vm_type"], "qemu", f"Agent {agent['id']} should be qemu VM")
            else:
                self.assertEqual(agent["vm_type"], "lxc", f"Agent {agent['id']} should be lxc container")

        # Check get_agent_vm_type function
        self.assertEqual(get_agent_vm_type({"type": "hermes"}), "qemu")
        self.assertEqual(get_agent_vm_type({"type": "openclaw"}), "qemu")
        self.assertEqual(get_agent_vm_type({"type": "antigravity"}), "lxc")
        self.assertEqual(get_agent_vm_type({"type": "codex"}), "lxc")
        self.assertEqual(get_agent_vm_type({"type": "ceo"}), "lxc")
        self.assertEqual(get_agent_vm_type({"type": "custom"}), "lxc")
        self.assertEqual(get_agent_vm_type({"type": "antigravity", "vm_type": "qemu"}), "qemu")

if __name__ == "__main__":
    unittest.main()
