---
name: convex-schema-validation
description: Best practices for designing relational schemas, indexes, and runtime validation with Convex's defineSchema and v validators.
---

# Convex Schema & Validation

## Overview
Convex uses TypeScript-first runtime schema definition in convex/schema.ts.

## Guidelines
1. Use defineSchema and defineTable.
2. Define indexes explicitly using .index("by_field", ["field"]).
3. Never use raw .any() when specific types (.string(), .boolean(), .array()) are known.
4. Use .optional(...) for nullable properties.