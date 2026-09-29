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
    signal: options.signal || AbortSignal.timeout(12000),
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

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");

  if (error) {
    return new NextResponse(
      `<!DOCTYPE html>
      <html>
      <head>
        <title>Google Sign-In Cancelled</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body { background: #07090e; color: #f87171; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
          .card { background: rgba(18, 24, 38, 0.9); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 20px; padding: 36px 30px; text-align: center; max-width: 440px; width: 100%; box-shadow: 0 20px 40px rgba(0,0,0,0.6); }
          h2 { margin: 0 0 12px; color: #fca5a5; font-size: 20px; }
          p { color: #94a3b8; font-size: 13px; line-height: 1.5; margin: 0 0 20px; }
          button { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 10px 24px; border-radius: 12px; cursor: pointer; font-size: 13px; }
        </style>
      </head>
      <body>
        <div class="card">
          <h2>Google Authorization Cancelled</h2>
          <p>${error}: ${errorDescription || "The authorization request was cancelled or denied."}</p>
          <button onclick="window.close()">Close Window</button>
        </div>
        <script>
          setTimeout(() => { if (window.opener) window.close(); }, 3500);
        </script>
      </body>
      </html>`,
      { headers: { "Content-Type": "text/html; charset=utf-8" }, status: 400 }
    );
  }

  if (!code) {
    return new NextResponse("Missing authorization code", { status: 400 });
  }

  try {
    const exchangeRes = await fetchCockpit("/api/google/auth/exchange_code", {
      method: "POST",
      body: JSON.stringify({
        code,
        redirect_uri: "https://workspace.webigo.ai/api/google/auth/callback",
      }),
    });

    if (exchangeRes && exchangeRes.ok) {
      const data = await exchangeRes.json();
      const email = data.profile?.email || "Google Account";

      return new NextResponse(
        `<!DOCTYPE html>
        <html>
        <head>
          <title>Google Account Connected</title>
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            body { background: #07090e; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
            .card { background: rgba(18, 24, 38, 0.9); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 24px; padding: 40px 32px; text-align: center; max-width: 440px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.7); }
            .icon { width: 56px; height: 56px; border-radius: 16px; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); color: #34d399; font-size: 26px; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 20px; }
            h2 { margin: 0 0 10px; font-size: 20px; font-weight: 700; color: #fff; }
            .pill { display: inline-block; padding: 6px 14px; border-radius: 999px; background: rgba(56, 189, 248, 0.1); color: #38bdf8; font-size: 13px; font-weight: 600; margin-bottom: 16px; border: 1px solid rgba(56, 189, 248, 0.2); }
            p { color: #94a3b8; font-size: 13px; line-height: 1.6; margin: 0 0 24px; }
            .stats { font-size: 12px; font-family: monospace; color: #34d399; margin-bottom: 24px; }
            button { background: #3b82f6; color: #fff; border: none; padding: 12px 24px; border-radius: 12px; cursor: pointer; font-size: 13px; font-weight: 600; width: 100%; }
          </style>
        </head>
        <body>
          <div class="card">
            <div class="icon">✓</div>
            <h2>Google Account Connected</h2>
            <div class="pill">${email}</div>
            <p>Your Google AI credentials and Gemini model quotas have been automatically deployed across all workspace agents in the cluster.</p>
            <div class="stats">✓ Proxmox Container Fleet Synchronized</div>
            <button onclick="done()">Close Window</button>
          </div>
          <script>
            function done() {
              if (window.opener) {
                window.opener.postMessage({ type: 'GOOGLE_AUTH_SUCCESS', email: '${email}' }, '*');
                window.close();
              } else {
                window.location.href = '/settings';
              }
            }
            setTimeout(done, 1500);
          </script>
        </body>
        </html>`,
        { headers: { "Content-Type": "text/html; charset=utf-8" }, status: 200 }
      );
    } else {
      const errText = exchangeRes ? await exchangeRes.text() : "Cluster API unreachable";
      return new NextResponse(
        `<!DOCTYPE html>
        <html>
        <head>
          <title>Token Exchange Failed</title>
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            body { background: #07090e; color: #f87171; font-family: sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }
            .card { background: rgba(18, 24, 38, 0.9); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 20px; padding: 32px; text-align: center; max-width: 460px; }
            h2 { margin: 0 0 12px; color: #fca5a5; font-size: 18px; }
            pre { background: #0b0f19; padding: 12px; border-radius: 8px; font-size: 11px; text-align: left; overflow-x: auto; color: #cbd5e1; }
            button { background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 10px 20px; border-radius: 10px; cursor: pointer; margin-top: 16px; }
          </style>
        </head>
        <body>
          <div class="card">
            <h2>OAuth Exchange Error</h2>
            <p style="font-size: 13px; color: #94a3b8;">Google authorization code received, but token exchange failed:</p>
            <pre>${errText}</pre>
            <button onclick="window.close()">Close Window</button>
          </div>
        </body>
        </html>`,
        { headers: { "Content-Type": "text/html; charset=utf-8" }, status: 502 }
      );
    }
  } catch (err: any) {
    return new NextResponse(`Error processing callback: ${err.message}`, { status: 500 });
  }
}
