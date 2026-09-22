---
name: vitest-testing
description: Comprehensive testing patterns for Vite, TypeScript, and Node.js projects using Vitest unit, integration, and mock testing.
---

# Vitest Testing Suite

## Overview
Blazing fast unit and integration testing powered by Vite.

## Rules & Patterns
1. Organize test files adjacent to code: [name].test.ts or inside __tests__/.
2. Use describe, it, expect from itest.
3. Mock external modules using i.mock(...) and spy on methods with i.spyOn(...).
4. Run tests with 
px vitest run or watch with 
px vitest.