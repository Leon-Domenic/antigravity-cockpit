import { NextRequest, NextResponse } from "next/server";
import { convexHttp } from "@/lib/convex";
import { api } from "@/convex/_generated/api";

const DEFAULT_AGENTS = [
  {
    agentId: "agent-1",
    vmid: 151,
    name: "Antigravity Prime",
    type: "antigravity",
    vmType: "lxc",
    role: "Architecture & Core Logic",
    ip: "192.168.178.169",
    port: 8000,
    vncPort: 6080,
    status: "idle",
  },
  {
    agentId: "agent-2",
    vmid: 152,
    name: "Antigravity SecOps",
    type: "antigravity",
    vmType: "lxc",
    role: "Code Review & Security Audits",
    ip: "192.168.178.170",
    port: 8000,
    vncPort: 6080,
    status: "idle",
  },
  {
    agentId: "agent-3",
    vmid: 153,
    name: "Codex Engine",
    type: "codex",
    vmType: "lxc",
    role: "API Integration & Test Automation",
    ip: "192.168.178.171",
    port: 8000,
    vncPort: 6080,
    status: "idle",
  },
  {
    agentId: "agent-5",
    vmid: 154,
    name: "Hermes Autonomous (KVM)",
    type: "hermes",
    vmType: "qemu",
    role: "End-to-End Execution & Self-Correction",
    ip: "192.168.178.172",
    port: 8000,
    vncPort: 6080,
    status: "idle",
  },
  {
    agentId: "agent-6",
    vmid: 155,
    name: "Open Claw Research (KVM)",
    type: "open-claw",
    vmType: "qemu",
    role: "Deep Research & Multi-Modal Browser",
    ip: "192.168.178.173",
    port: 8000,
    vncPort: 6080,
    status: "idle",
  },
];

export async function GET() {
  try {
    let agents = await convexHttp.query(api.agents.listAgents);
    if (!agents || agents.length === 0) {
      await convexHttp.mutation(api.agents.seedDefaultFleet);
      agents = await convexHttp.query(api.agents.listAgents);
    }
    return NextResponse.json(agents.length > 0 ? agents : DEFAULT_AGENTS);
  } catch (err: any) {
    return NextResponse.json(DEFAULT_AGENTS);
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { action, agentId, workspaceId, prompt } = body;

    if (action === "bind_workspace") {
      // Connect to agent bridge on container
      const agent = await convexHttp.query(api.agents.getAgent, { agentId });
      const targetIp = agent?.ip || "192.168.178.169";

      try {
        const bridgeRes = await fetch(`http://${targetIp}:8000/workspace/ensure`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workspace_path: "/home/ubuntu/workspace" }),
          signal: AbortSignal.timeout(4000),
        });
        const bridgeData = await bridgeRes.json();
        
        await convexHttp.mutation(api.agents.updateAgentStatus, {
          agentId,
          status: "idle",
          currentWorkspace: workspaceId,
        });

        return NextResponse.json({ success: true, bridge: bridgeData });
      } catch (bridgeErr: any) {
        return NextResponse.json({
          success: false,
          warning: `Agent bridge at ${targetIp}:8000 unreachable: ${bridgeErr.message}. Updated state in ConvexDB.`,
        });
      }
    }

    return NextResponse.json({ success: true });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
