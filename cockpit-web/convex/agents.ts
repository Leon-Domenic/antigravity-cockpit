import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const listAgents = query({
  handler: async (ctx) => {
    return await ctx.db.query("agents").collect();
  },
});

export const getAgent = query({
  args: { agentId: v.string() },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("agents")
      .withIndex("by_agentId", (q) => q.eq("agentId", args.agentId))
      .first();
  },
});

export const upsertAgent = mutation({
  args: {
    agentId: v.string(),
    vmid: v.number(),
    name: v.string(),
    type: v.string(),
    vmType: v.string(),
    role: v.string(),
    ip: v.string(),
    port: v.number(),
    vncPort: v.number(),
    status: v.string(),
    currentWorkspace: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agents")
      .withIndex("by_agentId", (q) => q.eq("agentId", args.agentId))
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        vmid: args.vmid,
        name: args.name,
        type: args.type,
        vmType: args.vmType,
        role: args.role,
        ip: args.ip,
        port: args.port,
        vncPort: args.vncPort,
        status: args.status,
        currentWorkspace: args.currentWorkspace,
        lastSeen: Date.now(),
      });
      return existing._id;
    } else {
      return await ctx.db.insert("agents", {
        agentId: args.agentId,
        vmid: args.vmid,
        name: args.name,
        type: args.type,
        vmType: args.vmType,
        role: args.role,
        ip: args.ip,
        port: args.port,
        vncPort: args.vncPort,
        status: args.status,
        currentWorkspace: args.currentWorkspace,
        lastSeen: Date.now(),
      });
    }
  },
});

export const updateAgentStatus = mutation({
  args: {
    agentId: v.string(),
    status: v.string(),
    currentWorkspace: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("agents")
      .withIndex("by_agentId", (q) => q.eq("agentId", args.agentId))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, {
        status: args.status,
        ...(args.currentWorkspace !== undefined ? { currentWorkspace: args.currentWorkspace } : {}),
        lastSeen: Date.now(),
      });
    }
  },
});

export const seedDefaultFleet = mutation({
  handler: async (ctx) => {
    const existing = await ctx.db.query("agents").collect();
    if (existing.length > 0) return;

    const defaultAgents = [
      {
        agentId: "agent-1",
        vmid: 151,
        name: "Antigravity Prime",
        type: "antigravity",
        vmType: "lxc",
        role: "Architecture & Core Logic",
        ip: "192.168.178.169",
        port: 8000,
        vncPort: 6080,
        status: "idle",
      },
      {
        agentId: "agent-2",
        vmid: 152,
        name: "Antigravity SecOps",
        type: "antigravity",
        vmType: "lxc",
        role: "Code Review & Security Audits",
        ip: "192.168.178.170",
        port: 8000,
        vncPort: 6080,
        status: "idle",
      },
      {
        agentId: "agent-3",
        vmid: 153,
        name: "Codex Engine",
        type: "codex",
        vmType: "lxc",
        role: "API Integration & Test Automation",
        ip: "192.168.178.171",
        port: 8000,
        vncPort: 6080,
        status: "idle",
      },
      {
        agentId: "agent-5",
        vmid: 154,
        name: "Hermes Autonomous (KVM)",
        type: "hermes",
        vmType: "qemu",
        role: "End-to-End Execution & Self-Correction",
        ip: "192.168.178.172",
        port: 8000,
        vncPort: 6080,
        status: "idle",
      },
      {
        agentId: "agent-6",
        vmid: 155,
        name: "Open Claw Research (KVM)",
        type: "open-claw",
        vmType: "qemu",
        role: "Deep Research & Multi-Modal Browser",
        ip: "192.168.178.173",
        port: 8000,
        vncPort: 6080,
        status: "idle",
      },
    ];

    for (const ag of defaultAgents) {
      await ctx.db.insert("agents", {
        ...ag,
        lastSeen: Date.now(),
      });
    }
  },
});
