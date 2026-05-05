import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const backendUrl = "http://65.1.207.29:8000";

  // Forward the Authorization header from the incoming request
  const authHeader = request.headers.get("authorization") || "";

  try {
    const res = await fetch(`${backendUrl}/api/audits`, {
      method: "GET",
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Audits proxy error:", err);
    return NextResponse.json({ detail: "Backend unreachable" }, { status: 502 });
  }
}
