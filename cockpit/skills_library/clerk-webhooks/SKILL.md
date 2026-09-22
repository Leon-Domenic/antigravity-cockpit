---
name: clerk-webhooks
description: Guide for receiving and verifying Clerk webhook events (e.g. user.created, user.updated) securely using Svix headers.
---

# Clerk Webhook Verification & Processing

## Overview
Handle asynchronous user lifecycle events from Clerk to keep internal databases synchronized.

## Key Rules
1. Read Svix headers: svix-id, svix-timestamp, svix-signature.
2. Verify HMAC signature using 
ew Webhook(SIGNING_SECRET).verify(...).
3. Handle idempotency: track event IDs to prevent duplicate processing.