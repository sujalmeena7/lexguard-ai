import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const backendUrl = "http://65.1.207.29:8000";

  try {
    // Forward multipart form data to backend upload endpoint
    const formData = await request.formData();

    const res = await fetch(`${backendUrl}/api/analyze/upload`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Analyze proxy error:", err);
    return NextResponse.json(
      { detail: "Backend unreachable" },
      { status: 502 }
    );
  }
}
