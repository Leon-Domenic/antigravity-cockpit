import { NextRequest, NextResponse } from "next/server";
import { convexHttp } from "@/lib/convex";
import { api } from "@/convex/_generated/api";

export async function GET() {
  try {
    const config = await convexHttp.query(api.git.getGitConfig);
    return NextResponse.json(config);
  } catch (err: any) {
    return NextResponse.json({
      provider: "github",
      token: "",
      hasToken: false,
      username: "",
      email: "",
      error: err.message,
    });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { provider = "github", token, username = "", email = "" } = body;

    await convexHttp.mutation(api.git.saveGitConfig, {
      provider,
      token,
      username,
      email,
    });

    return NextResponse.json({ success: true, message: "Git configuration updated in ConvexDB" });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
