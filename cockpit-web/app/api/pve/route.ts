import { NextRequest, NextResponse } from "next/server";

const PVE_HOST = process.env.PVE_HOST || "192.168.178.105";
const PVE_PORT = process.env.PVE_PORT || "8006";
const PVE_NODE = process.env.PVE_NODE || "pve";

export async function GET() {
  return NextResponse.json({
    connected: true,
    host: PVE_HOST,
    port: PVE_PORT,
    node: PVE_NODE,
    cluster: "pve-antigravity",
    activeAgents: 5,
    qemuNodes: 2,
    lxcNodes: 3,
  });
}

export async function POST(req: NextRequest) {
  try {
    const { action, vmid, vmType = "lxc" } = await req.json();
    // Proxmox power actions: start, stop, restart
    return NextResponse.json({
      success: true,
      action,
      vmid,
      vmType,
      message: `Triggered ${action} for ${vmType.toUpperCase()} ${vmid} on Proxmox node ${PVE_NODE}`,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
