import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getGitConfig = query({
  args: {
    userId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    let config = null;
    if (args.userId) {
      config = await ctx.db
        .query("gitConfigs")
        .withIndex("by_user", (q) => q.eq("userId", args.userId))
        .first();
    }
    // Fallback to cluster default if user has not set their own
    if (!config) {
      config = await ctx.db.query("gitConfigs").first();
    }

    if (!config) {
      return {
        provider: "github",
        token: "",
        username: "",
        email: "",
        hasToken: false,
      };
    }

    // Mask token for frontend display
    const masked = config.token
      ? config.token.slice(0, 4) + "••••••••" + config.token.slice(-4)
      : "";

    return {
      provider: config.provider,
      token: masked,
      hasToken: Boolean(config.token),
      username: config.username,
      email: config.email,
      updatedAt: config.updatedAt,
    };
  },
});

export const getRawGitToken = query({
  args: {
    userId: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    // Used by internal server API routes to authenticate git clone/push
    let config = null;
    if (args.userId) {
      config = await ctx.db
        .query("gitConfigs")
        .withIndex("by_user", (q) => q.eq("userId", args.userId))
        .first();
    }
    if (!config) {
      config = await ctx.db.query("gitConfigs").first();
    }
    return config?.token || "";
  },
});

export const saveGitConfig = mutation({
  args: {
    userId: v.optional(v.string()),
    provider: v.string(),
    token: v.optional(v.string()),
    username: v.string(),
    email: v.string(),
  },
  handler: async (ctx, args) => {
    let existing = null;
    if (args.userId) {
      existing = await ctx.db
        .query("gitConfigs")
        .withIndex("by_user", (q) => q.eq("userId", args.userId))
        .first();
    } else {
      existing = await ctx.db.query("gitConfigs").first();
    }

    const tokenToSave = args.token !== undefined && args.token !== ""
      ? args.token
      : (existing?.token || "");

    if (existing) {
      await ctx.db.patch(existing._id, {
        userId: args.userId,
        provider: args.provider,
        token: tokenToSave,
        username: args.username,
        email: args.email,
        updatedAt: Date.now(),
      });
      return existing._id;
    } else {
      return await ctx.db.insert("gitConfigs", {
        userId: args.userId,
        provider: args.provider,
        token: tokenToSave,
        username: args.username,
        email: args.email,
        updatedAt: Date.now(),
      });
    }
  },
});
