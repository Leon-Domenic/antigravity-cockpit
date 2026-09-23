import { ConvexHttpClient } from "convex/browser";

const convexUrl = process.env.NEXT_PUBLIC_CONVEX_URL || "http://127.0.0.1:3210";

// Server-side HTTP Convex client (for NextAuth callbacks and API route handlers)
export const convexHttp = new ConvexHttpClient(convexUrl);
