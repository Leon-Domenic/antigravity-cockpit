import { NextRequest, NextResponse } from "next/server";
import { convexHttp } from "@/lib/convex";
import { api } from "@/convex/_generated/api";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs";
import path from "path";

const execAsync = promisify(exec);

const WORKSPACES_DIR = process.env.COCKPIT_WORKSPACES_DIR || 
  (process.platform === "win32" ? path.join(process.cwd(), "..", "workspaces_data") : "/home/ubuntu/workspaces_data");

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await req.json();
    const { action, commitMessage, authorName, authorEmail, branch = "main" } = body;

    const workspace = await convexHttp.query(api.workspaces.getWorkspace, { id: params.id as any });
    if (!workspace) {
      return NextResponse.json({ error: "Workspace not found" }, { status: 404 });
    }

    const targetDir = path.join(WORKSPACES_DIR, workspace.name.replace(/[^a-zA-Z0-9_-]/g, "_"));
    if (!fs.existsSync(targetDir)) {
      return NextResponse.json({ error: `Directory ${targetDir} does not exist` }, { status: 404 });
    }

    let token = "";
    try {
      token = await convexHttp.query(api.git.getRawGitToken);
    } catch (_) {}

    if (action === "pull") {
      const { stdout } = await execAsync(`git -C "${targetDir}" pull origin ${branch}`);
      const { stdout: commitHash } = await execAsync(`git -C "${targetDir}" rev-parse --short HEAD`);
      const { stdout: commitMsg } = await execAsync(`git -C "${targetDir}" log -1 --pretty=%B`);
      const { stdout: commitAuthor } = await execAsync(`git -C "${targetDir}" log -1 --pretty=%an`);

      await convexHttp.mutation(api.workspaces.recordGitCommit, {
        id: params.id as any,
        gitCommit: commitHash.trim(),
        gitCommitMsg: commitMsg.trim(),
        gitCommitAuthor: commitAuthor.trim(),
      });

      return NextResponse.json({
        success: true,
        output: stdout.trim(),
        commit: commitHash.trim(),
      });
    }

    if (action === "commit") {
      if (!commitMessage) {
        return NextResponse.json({ error: "Commit message is required" }, { status: 400 });
      }

      const name = authorName || "Antigravity Agent";
      const email = authorEmail || "agent@antigravity.cockpit";

      await execAsync(`git -C "${targetDir}" config user.name "${name}"`);
      await execAsync(`git -C "${targetDir}" config user.email "${email}"`);
      await execAsync(`git -C "${targetDir}" add -A`);
      
      const { stdout } = await execAsync(`git -C "${targetDir}" commit -m "${commitMessage.replace(/"/g, '\\"')}"`);
      const { stdout: commitHash } = await execAsync(`git -C "${targetDir}" rev-parse --short HEAD`);

      await convexHttp.mutation(api.workspaces.recordGitCommit, {
        id: params.id as any,
        gitCommit: commitHash.trim(),
        gitCommitMsg: commitMessage.trim(),
        gitCommitAuthor: name,
      });

      return NextResponse.json({
        success: true,
        output: stdout.trim(),
        commit: commitHash.trim(),
      });
    }

    if (action === "push") {
      let pushCmd = `git -C "${targetDir}" push origin ${branch}`;
      if (token && workspace.gitUrl?.startsWith("https://github.com/")) {
        const authedRemote = workspace.gitUrl.replace("https://github.com/", `https://oauth2:${token}@github.com/`);
        pushCmd = `git -C "${targetDir}" push "${authedRemote}" ${branch}`;
      }

      const { stdout, stderr } = await execAsync(pushCmd);
      return NextResponse.json({
        success: true,
        output: (stdout || stderr).trim(),
      });
    }

    if (action === "status") {
      const { stdout } = await execAsync(`git -C "${targetDir}" status --short`);
      return NextResponse.json({
        success: true,
        status: stdout.trim(),
      });
    }

    return NextResponse.json({ error: "Unsupported git action" }, { status: 400 });
  } catch (err: any) {
    console.error("[API Workspaces Git Action] Error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
