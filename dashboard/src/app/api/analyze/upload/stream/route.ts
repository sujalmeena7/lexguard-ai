import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const backendUrl = "http://65.1.207.29:8000";
  const authHeader = request.headers.get("authorization") || "";

  try {
    const formData = await request.formData();

    const res = await fetch(`${backendUrl}/api/analyze/upload/stream`, {
      method: "POST",
      headers: {
        ...(authHeader ? { Authorization: authHeader } : {}),
      },
      body: formData,
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "Backend error");
      return new NextResponse(text, { status: res.status });
    }

    // Forward SSE stream directly
    return new NextResponse(res.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    console.error("Analyze stream proxy error:", err);
    return NextResponse.json(
      { detail: "Backend unreachable" },
      { status: 502 }
    );
  }
}
