import { NextResponse } from "next/server";
import { refreshCandidates } from "@/lib/api";

export async function POST() {
  try {
    const result = await refreshCandidates();
    return NextResponse.json(result);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Refresh failed";
    return NextResponse.json({ detail: msg }, { status: 500 });
  }
}
