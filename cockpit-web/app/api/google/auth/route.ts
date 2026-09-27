import { NextRequest, NextResponse } from "next/server";

const COCKPIT_URL = process.env.COCKPIT_BACKEND_URL || "http://192.168.178.168:3000";

export async function GET(req: NextRequest) {
  try {
    const res = await fetch(`${COCKPIT_URL}/api/google/auth`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }
  } catch (err: any) {
    // If Cockpit server is unreachable (e.g. edge worker without VPN)
  }

  return NextResponse.json({
    authenticated: false,
    email: null,
    name: null,
    picture: null,
    tier: "Antigravity",
    last_synced: null,
    expires_at: null,
    is_expired: false,
    offline: true,
  });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { action, token_json } = body;

    if (action === "login_url") {
      const res = await fetch(`${COCKPIT_URL}/api/google/auth/login_url`, {
        signal: AbortSignal.timeout(4000),
      });
      const data = await res.json();
      return NextResponse.json(data);
    }

    if (action === "sync") {
      const res = await fetch(`${COCKPIT_URL}/api/google/auth/sync`, {
        method: "POST",
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json();
      return NextResponse.json(data);
    }

    if (action === "refresh") {
      const res = await fetch(`${COCKPIT_URL}/api/google/auth/refresh`, {
        method: "POST",
        signal: AbortSignal.timeout(10000),
      });
      const data = await res.json();
      return NextResponse.json(data);
    }

    if (action === "disconnect") {
      const res = await fetch(`${COCKPIT_URL}/api/google/auth`, {
        method: "DELETE",
        signal: AbortSignal.timeout(5000),
      });
      const data = await res.json();
      return NextResponse.json(data);
    }

    // Default: Save token
    const res = await fetch(`${COCKPIT_URL}/api/google/auth`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token_json }),
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json(
      { error: `Cockpit Cluster Gateway Error: ${err.message}` },
      { status: 502 }
    );
  }
}
