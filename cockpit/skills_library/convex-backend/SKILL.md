---
name: convex-backend
description: Comprehensive guidelines for building reactive backends with Convex including queries, mutations, actions, and optimistic updates.
---

# Convex Backend Development

## Overview
Convex is a reactive backend-as-a-service. All queries are pure, deterministic, and automatically reactive. Mutations are atomic database transactions. Actions handle third-party APIs and non-deterministic side-effects.

## Core Rules
1. **Queries (query)**: Must be pure and deterministic. Never call third-party APIs, generate random numbers, or perform async side-effects in queries.
2. **Mutations (mutation)**: Atomic and transactional. Use for writing/updating database tables using ctx.db.
3. **Actions (ction)**: Use for calling external fetch APIs, AI models, payment gateways, etc. Can call queries and mutations via ctx.runQuery and ctx.runMutation.
4. **Schemas (schema.ts)**: Always define schema in convex/schema.ts using defineSchema and defineTable with strict validators (.string(), .number(), .id(), etc.).