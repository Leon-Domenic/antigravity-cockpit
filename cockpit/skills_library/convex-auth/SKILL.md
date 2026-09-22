---
name: convex-auth
description: Patterns for setting up secure authentication, JWT verification, and user identity management in Convex backends.
---

# Convex Authentication & Identity

## Overview
Handle user identity securely in Convex queries, mutations, and actions using ctx.auth.

## Guidelines
1. Access authenticated user via wait ctx.auth.getUserIdentity().
2. Always verify identity at the start of protected mutations/queries:
   `	s
   const identity = await ctx.auth.getUserIdentity();
   if (!identity) throw new Error("Unauthorized");
   `
3. Link external auth provider subjects (identity.subject) to internal user tables with unique indexes.