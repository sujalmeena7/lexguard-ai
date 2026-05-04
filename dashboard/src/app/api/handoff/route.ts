import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json();
  // Hardcoded EC2 backend URL — must match landing page widget backend
  const backendUrl = "http://65.1.207.29:8000";

  try {
    const res = await fetch(`${backendUrl}/api/auth/handoff/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Handoff proxy error:", err);
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}
