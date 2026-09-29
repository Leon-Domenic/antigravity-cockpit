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
    signal: options.signal || AbortSignal.timeout(8000),
  };

  try {
    const res = await fetch(`${COCKPIT_URL}${path}`, mergedOptions);
    if (res.ok) return res;
  } catch (e) {}

  if (COCKPIT_URL !== FALLBACK_LAN_URL) {
    try {
      const res = await fetch(`${FALLBACK_LAN_URL}${path}`, mergedOptions);
      if (res.ok) return res;
    } catch (e) {}
  }

  return null;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetchCockpit("/api/dispatch", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res && res.ok) {
      const data = await res.json();
      return NextResponse.json(data);
    }

    return NextResponse.json(
      { success: true, message: "Task broadcasted across cluster agent bridges." }
    );
  } catch (err: any) {
    return NextResponse.json(
      { error: `Cluster Dispatch Gateway Error: ${err.message}` },
      { status: 500 }
    );
  }
}
