import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const listWorkspaces = query({
  args: {
    userId: v.optional(v.string()),
    role: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const all = await ctx.db.query("workspaces").order("desc").collect();
    // If admin or no userId specified, return all
    if (!args.userId || args.role === "admin") {
      return all;
    }
    // Filter to workspaces owned by the user or marked as shared
    return all.filter((ws) => ws.userId === args.userId || ws.isShared === true);
  },
});

export const getWorkspace = query({
  args: { id: v.id("workspaces") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.id);
  },
});

export const createWorkspace = mutation({
  args: {
    userId: v.optional(v.string()),
    ownerEmail: v.optional(v.string()),
    isShared: v.optional(v.boolean()),
    name: v.string(),
    description: v.optional(v.string()),
    source: v.string(),
    gitUrl: v.optional(v.string()),
    gitBranch: v.optional(v.string()),
    gitCommit: v.optional(v.string()),
    gitCommitMsg: v.optional(v.string()),
    gitCommitAuthor: v.optional(v.string()),
    fileCount: v.number(),
    dirCount: v.number(),
    sizeBytes: v.number(),
    primaryLanguage: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const id = await ctx.db.insert("workspaces", {
      userId: args.userId,
      ownerEmail: args.ownerEmail,
      isShared: args.isShared ?? false,
      name: args.name,
      description: args.description || "",
      source: args.source,
      gitUrl: args.gitUrl,
      gitBranch: args.gitBranch || "main",
      gitCommit: args.gitCommit,
      gitCommitMsg: args.gitCommitMsg,
      gitCommitAuthor: args.gitCommitAuthor,
      syncedAgents: [],
      fileCount: args.fileCount,
      dirCount: args.dirCount,
      sizeBytes: args.sizeBytes,
      primaryLanguage: args.primaryLanguage || "TypeScript",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
    return id;
  },
});

export const updateWorkspace = mutation({
  args: {
    id: v.id("workspaces"),
    description: v.optional(v.string()),
    gitCommit: v.optional(v.string()),
    gitCommitMsg: v.optional(v.string()),
    gitCommitAuthor: v.optional(v.string()),
    fileCount: v.optional(v.number()),
    dirCount: v.optional(v.number()),
    sizeBytes: v.optional(v.number()),
    primaryLanguage: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const { id, ...patch } = args;
    await ctx.db.patch(id, {
      ...patch,
      updatedAt: Date.now(),
    });
  },
});

export const recordGitCommit = mutation({
  args: {
    id: v.id("workspaces"),
    gitCommit: v.string(),
    gitCommitMsg: v.string(),
    gitCommitAuthor: v.string(),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.id, {
      gitCommit: args.gitCommit,
      gitCommitMsg: args.gitCommitMsg,
      gitCommitAuthor: args.gitCommitAuthor,
      updatedAt: Date.now(),
    });
  },
});

export const markSyncedAgent = mutation({
  args: {
    id: v.id("workspaces"),
    agentId: v.string(),
  },
  handler: async (ctx, args) => {
    const ws = await ctx.db.get(args.id);
    if (!ws) return;
    const currentList = ws.syncedAgents || [];
    if (!currentList.includes(args.agentId)) {
      await ctx.db.patch(args.id, {
        syncedAgents: [...currentList, args.agentId],
        updatedAt: Date.now(),
      });
    }
  },
});

export const deleteWorkspace = mutation({
  args: { id: v.id("workspaces") },
  handler: async (ctx, args) => {
    await ctx.db.delete(args.id);
  },
});
