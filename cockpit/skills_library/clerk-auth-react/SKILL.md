---
name: clerk-auth-react
description: Best practices for embedding Clerk authentication into React and Vite single-page applications with seamless session management.
---

# Clerk Authentication with React & Vite

## Overview
Integrate Clerk auth into React frontends using @clerk/clerk-react.

## Key Patterns
1. Wrap root with <ClerkProvider publishableKey={PUBLISHABLE_KEY}>.
2. Protect UI with <SignedIn> and <SignedOut> components.
3. Access session state and user details with useUser(), useAuth(), and useClerk().
4. Forward Clerk JWT token to backend APIs with wait getToken().