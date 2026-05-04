// Vercel Serverless Function — Proxy /api/auth/handoff to EC2 backend
const _DEFAULT_URL = process.env.BACKEND_URL_INSECURE || "http://65.1.207.29:8000";
const BACKEND_URL = process.env.BACKEND_URL || (process.env.NODE_ENV === "production" ? (() => { throw new Error("BACKEND_URL env var is required in production"); })() : _DEFAULT_URL);

export default async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token");
    return res.status(204).end();
  }

  const headers = Object.fromEntries(
    ["content-type", "authorization", "x-admin-token"]
      .filter(k => req.headers[k])
      .map(k => [k, req.headers[k]])
  );

  const fetchOptions = { method: req.method, headers };

  if (["POST", "PUT", "PATCH"].includes(req.method) && req.body) {
    fetchOptions.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
  }

  try {
    const backendRes = await fetch(`${BACKEND_URL}/api/auth/handoff`, fetchOptions);

    res.setHeader("Access-Control-Allow-Origin", "*");
    const ct = backendRes.headers.get("content-type");
    if (ct) res.setHeader("Content-Type", ct);
    res.status(backendRes.status);
    res.send(await backendRes.text());
  } catch (err) {
    res.status(502).json({ detail: "Backend unreachable", error: err.message });
  }
}
