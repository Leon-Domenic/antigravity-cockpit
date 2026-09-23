import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  users: defineTable({
    name: v.string(),
    email: v.string(),
    passwordHash: v.string(),
    role: v.string(), // "admin" | "developer" | "guest"
    image: v.optional(v.string()),
    createdAt: v.number(),
  }).index("by_email", ["email"]),

  sessions: defineTable({
    userId: v.id("users"),
    sessionToken: v.string(),
    expires: v.number(),
  }).index("by_token", ["sessionToken"]),

  accounts: defineTable({
    userId: v.id("users"),
    type: v.string(),
    provider: v.string(),
    providerAccountId: v.string(),
    accessToken: v.optional(v.string()),
    refreshToken: v.optional(v.string()),
  }).index("by_provider_account", ["provider", "providerAccountId"]),

  workspaces: defineTable({
    userId: v.optional(v.string()),
    ownerEmail: v.optional(v.string()),
    isShared: v.optional(v.boolean()),
    name: v.string(),
    description: v.optional(v.string()),
    source: v.string(), // "git" | "upload" | "template"
    gitUrl: v.optional(v.string()),
    gitBranch: v.optional(v.string()),
    gitCommit: v.optional(v.string()),
    gitCommitMsg: v.optional(v.string()),
    gitCommitAuthor: v.optional(v.string()),
    syncedAgents: v.array(v.string()),
    fileCount: v.number(),
    dirCount: v.number(),
    sizeBytes: v.number(),
    primaryLanguage: v.optional(v.string()),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_user", ["userId"]),

  gitConfigs: defineTable({
    userId: v.optional(v.string()),
    provider: v.string(), // "github" | "gitlab" | "custom"
    token: v.string(),
    username: v.string(),
    email: v.string(),
    updatedAt: v.number(),
  }).index("by_user", ["userId"]),

  agents: defineTable({
    agentId: v.string(),
    vmid: v.number(),
    name: v.string(),
    type: v.string(), // "antigravity" | "codex" | "hermes" | "open-claw"
    vmType: v.string(), // "lxc" | "qemu"
    role: v.string(),
    ip: v.string(),
    port: v.number(),
    vncPort: v.number(),
    status: v.string(), // "running" | "stopped" | "idle" | "busy"
    currentWorkspace: v.optional(v.string()),
    currentUserId: v.optional(v.string()),
    lastSeen: v.number(),
  }).index("by_agentId", ["agentId"]),

  workOrders: defineTable({
    userId: v.optional(v.string()),
    creatorEmail: v.optional(v.string()),
    title: v.string(),
    directive: v.string(),
    assignedTo: v.string(),
    workspaceId: v.optional(v.string()),
    status: v.string(), // "pending" | "in_progress" | "completed" | "failed"
    createdAt: v.number(),
    completedAt: v.optional(v.number()),
  }),

  auditLogs: defineTable({
    action: v.string(),
    actor: v.string(),
    details: v.string(),
    timestamp: v.number(),
  }),
});
