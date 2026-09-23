import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { convexHttp } from "@/lib/convex";
import { api } from "@/convex/_generated/api";
import { exec } from "child_process";
import { promisify } from "util";
import fs from "fs";
import path from "path";

const execAsync = promisify(exec);

const WORKSPACES_BASE_DIR = process.env.COCKPIT_WORKSPACES_DIR || 
  (process.platform === "win32" ? path.join(process.cwd(), "..", "workspaces_data") : "/home/ubuntu/workspaces_data");

function countFiles(dir: string): { files: number; dirs: number; size: number } {
  let files = 0;
  let dirs = 0;
  let size = 0;

  if (!fs.existsSync(dir)) return { files, dirs, size };

  function traverse(current: string) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name === ".git" || entry.name === "node_modules") continue;
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        dirs++;
        traverse(full);
      } else if (entry.isFile()) {
        files++;
        try {
          size += fs.statSync(full).size;
        } catch (_) {}
      }
    }
  }

  traverse(dir);
  return { files, dirs, size };
}

export async function GET(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id;
    const role = (session?.user as any)?.role;

    const list = await convexHttp.query(api.workspaces.listWorkspaces, {
      userId,
      role,
    });
    return NextResponse.json(list);
  } catch (err: any) {
    return NextResponse.json([], { status: 200 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const session = await getServerSession(authOptions);
    const userId = (session?.user as any)?.id || "admin-root";
    const ownerEmail = session?.user?.email || "admin@antigravity.cockpit";

    const body = await req.json();
    const { name, description = "", gitUrl, gitBranch = "main", isShared = false } = body;

    if (!name) {
      return NextResponse.json({ error: "Workspace name is required" }, { status: 400 });
    }

    // Partition workspace directory per user: workspaces_data/<user>/<workspace_name>
    const userDirKey = ownerEmail.replace(/[^a-zA-Z0-9_-]/g, "_");
    const userWorkspaceDir = path.join(WORKSPACES_BASE_DIR, userDirKey);
    if (!fs.existsSync(userWorkspaceDir)) {
      fs.mkdirSync(userWorkspaceDir, { recursive: true });
    }

    const targetDir = path.join(userWorkspaceDir, name.replace(/[^a-zA-Z0-9_-]/g, "_"));
    let gitCommit = "initial";
    let gitCommitMsg = "Initial workspace setup";
    let gitCommitAuthor = session?.user?.name || ownerEmail;

    if (gitUrl) {
      // Check for user-scoped or cluster private git token
      let token = "";
      try {
        token = await convexHttp.query(api.git.getRawGitToken, { userId });
      } catch (_) {}

      let authenticatedUrl = gitUrl;
      if (token && gitUrl.startsWith("https://github.com/")) {
        authenticatedUrl = gitUrl.replace("https://github.com/", `https://oauth2:${token}@github.com/`);
      }

      if (fs.existsSync(targetDir)) {
        await execAsync(`git -C "${targetDir}" pull origin ${gitBranch}`);
      } else {
        await execAsync(`git clone --depth 50 --branch ${gitBranch} "${authenticatedUrl}" "${targetDir}"`);
      }

      try {
        const { stdout: commitHash } = await execAsync(`git -C "${targetDir}" rev-parse --short HEAD`);
        const { stdout: commitMsg } = await execAsync(`git -C "${targetDir}" log -1 --pretty=%B`);
        const { stdout: commitAuthor } = await execAsync(`git -C "${targetDir}" log -1 --pretty=%an`);
        gitCommit = commitHash.trim();
        gitCommitMsg = commitMsg.trim();
        gitCommitAuthor = commitAuthor.trim();
      } catch (_) {}
    } else {
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true });
        fs.writeFileSync(path.join(targetDir, "README.md"), `# ${name}\n\n${description}\n\nOwner: ${ownerEmail}\n`);
      }
    }

    const { files, dirs, size } = countFiles(targetDir);

    // Persist with owner identity and sharing settings in ConvexDB
    const id = await convexHttp.mutation(api.workspaces.createWorkspace, {
      userId,
      ownerEmail,
      isShared,
      name,
      description,
      source: gitUrl ? "git" : "template",
      gitUrl: gitUrl || undefined,
      gitBranch,
      gitCommit,
      gitCommitMsg,
      gitCommitAuthor,
      fileCount: files,
      dirCount: dirs,
      sizeBytes: size,
      primaryLanguage: "TypeScript",
    });

    return NextResponse.json({
      success: true,
      id,
      name,
      ownerEmail,
      gitCommit,
      fileCount: files,
      sizeBytes: size,
    });
  } catch (err: any) {
    console.error("[API Workspaces POST] Error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
