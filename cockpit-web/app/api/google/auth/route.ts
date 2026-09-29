import { NextRequest, NextResponse } from "next/server";

const COCKPIT_URL = process.env.COCKPIT_BACKEND_URL || "https://cockpit.webigo.ai";
const FALLBACK_LAN_URL = "http://192.168.178.168:3000";
const COCKPIT_SECRET = process.env.COCKPIT_INTERNAL_KEY || "webigo_cockpit_internal_cluster_secret_2026";

function getHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${COCKPIT_SECRET}`,
    "X-Cockpit-Internal-Key": COCKPIT_SECRET,
  };
}

async function fetchCockpit(path: string, options: RequestInit = {}) {
  const mergedOptions: RequestInit = {
    ...options,
    headers: {
      ...getHeaders(),
      ...(options.headers || {}),
    },
    signal: options.signal || AbortSignal.timeout(6000),
  };

  try {
    const res = await fetch(`${COCKPIT_URL}${path}`, mergedOptions);
    if (res.ok) return res;
  } catch (e) {
    // Primary failed, try LAN fallback if available
  }

  if (COCKPIT_URL !== FALLBACK_LAN_URL) {
    try {
      const res = await fetch(`${FALLBACK_LAN_URL}${path}`, mergedOptions);
      if (res.ok) return res;
    } catch (e) {}
  }

  return null;
}

export async function GET(req: NextRequest) {
  try {
    const res = await fetchCockpit("/api/google/auth", { cache: "no-store" });
    if (res && res.ok) {
      const data = await res.json();
      return NextResponse.json({
        ...data,
        authenticated: Boolean(data.authenticated || data.configured),
        configured: Boolean(data.configured || data.authenticated),
        offline: false,
      });
    }
  } catch (err: any) {}

  return NextResponse.json({
    authenticated: false,
    configured: false,
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
      const res = await fetchCockpit("/api/google/auth/login_url");
      if (res && res.ok) return NextResponse.json(await res.json());
      return NextResponse.json({ error: "Failed to reach Cockpit login URL endpoint" }, { status: 502 });
    }

    if (action === "get_oauth_config") {
      const res = await fetchCockpit("/api/google/auth/oauth_config");
      if (res && res.ok) return NextResponse.json(await res.json());
      return NextResponse.json({
        client_id: "",
        has_secret: false,
        redirect_uri: "https://workspace.webigo.ai/api/google/auth/callback"
      });
    }

    if (action === "save_oauth_config") {
      const { client_id, client_secret } = body;
      const res = await fetchCockpit("/api/google/auth/oauth_config", {
        method: "POST",
        body: JSON.stringify({ client_id, client_secret }),
      });
      if (res && res.ok) return NextResponse.json(await res.json());
      return NextResponse.json({ error: "Failed to save OAuth configuration" }, { status: 502 });
    }

    if (action === "sync") {
      const res = await fetchCockpit("/api/google/auth/sync", { method: "POST" });
      if (res && res.ok) return NextResponse.json(await res.json());
      return NextResponse.json({ error: "Failed to dispatch fleet sync" }, { status: 502 });
    }

    if (action === "refresh") {
      const res = await fetchCockpit("/api/google/auth/refresh", { method: "POST" });
      if (res && res.ok) return NextResponse.json(await res.json());
      return NextResponse.json({ error: "Failed to execute token refresh" }, { status: 502 });
    }

    if (action === "disconnect") {
      const res = await fetchCockpit("/api/google/auth", { method: "DELETE" });
      if (res && res.ok) return NextResponse.json(await res.json());
      return NextResponse.json({ error: "Failed to disconnect Google Auth" }, { status: 502 });
    }

    // Default: Save token
    const res = await fetchCockpit("/api/google/auth", {
      method: "POST",
      body: JSON.stringify({ token_json }),
    });
    if (res && res.ok) return NextResponse.json(await res.json());
    return NextResponse.json({ error: "Failed to persist token to Cockpit" }, { status: 502 });
  } catch (err: any) {
    return NextResponse.json(
      { error: `Cockpit Cluster Gateway Error: ${err.message}` },
      { status: 502 }
    );
  }
}
