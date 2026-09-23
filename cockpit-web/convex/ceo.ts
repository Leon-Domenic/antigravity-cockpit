import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const listWorkOrders = query({
  handler: async (ctx) => {
    return await ctx.db.query("workOrders").order("desc").collect();
  },
});

export const createWorkOrder = mutation({
  args: {
    title: v.string(),
    directive: v.string(),
    assignedTo: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("workOrders", {
      title: args.title,
      directive: args.directive,
      assignedTo: args.assignedTo,
      status: "pending",
      createdAt: Date.now(),
    });
  },
});

export const updateWorkOrderStatus = mutation({
  args: {
    id: v.id("workOrders"),
    status: v.string(),
  },
  handler: async (ctx, args) => {
    const patch: { status: string; completedAt?: number } = {
      status: args.status,
    };
    if (args.status === "completed" || args.status === "failed") {
      patch.completedAt = Date.now();
    }
    await ctx.db.patch(args.id, patch);
  },
});
