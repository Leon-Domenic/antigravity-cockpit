import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const listLogs = query({
  handler: async (ctx) => {
    return await ctx.db.query("auditLogs").order("desc").take(50);
  },
});

export const logAction = mutation({
  args: {
    action: v.string(),
    actor: v.string(),
    details: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("auditLogs", {
      action: args.action,
      actor: args.actor,
      details: args.details,
      timestamp: Date.now(),
    });
  },
});
