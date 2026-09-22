---
name: clerk-nextjs
description: Complete guide for configuring Clerk in Next.js App Router, middleware protection, and server-side authentication.
---

# Clerk Authentication with Next.js App Router

## Overview
Use @clerk/nextjs for Next.js applications supporting Server Components, Route Handlers, and Server Actions.

## Key Rules
1. Implement clerkMiddleware in middleware.ts.
2. Use createRouteMatcher to define public vs protected routes.
3. In Server Components, call wait auth() to get user ID and session claims.