import { NextRequest, NextResponse } from "next/server";
import { convexHttp } from "@/lib/convex";
import { api } from "@/convex/_generated/api";

export async function GET() {
  try {
    const orders = await convexHttp.query(api.ceo.listWorkOrders);
    return NextResponse.json(orders);
  } catch (err: any) {
    return NextResponse.json([], { status: 200 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const { title, directive, assignedTo } = await req.json();
    const id = await convexHttp.mutation(api.ceo.createWorkOrder, {
      title,
      directive,
      assignedTo,
    });
    return NextResponse.json({ success: true, id });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
