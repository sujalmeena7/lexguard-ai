// Vercel Serverless Function — Proxy /api/* to EC2 backend
// This avoids mixed-content (HTTPS→HTTP) blocking in browsers.
const BACKEND_URL = "http://65.1.207.29:8000";

export default async function handler(req, res) {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token");
    res.setHeader("Access-Control-Max-Age", "600");
    return res.status(204).end();
  }

  const { path } = req.query;
  const backendPath = Array.isArray(path) ? path.join("/") : path || "";
  const url = `${BACKEND_URL}/api/${backendPath}`;

  // Forward query params (except the internal 'path' param)
  const qp = new URLSearchParams(req.query);
  qp.delete("path");
  const qs = qp.toString();
  const fullUrl = qs ? `${url}?${qs}` : url;

  // Build headers to forward
  const headers = {};
  if (req.headers["content-type"]) headers["Content-Type"] = req.headers["content-type"];
  if (req.headers["authorization"]) headers["Authorization"] = req.headers["authorization"];
  if (req.headers["x-admin-token"]) headers["X-Admin-Token"] = req.headers["x-admin-token"];

  const fetchOptions = {
    method: req.method,
    headers,
  };

  // Forward body for POST/PUT/PATCH
  if (["POST", "PUT", "PATCH"].includes(req.method) && req.body) {
    fetchOptions.body = typeof req.body === "string" ? req.body : JSON.stringify(req.body);
  }

  try {
    const backendRes = await fetch(fullUrl, fetchOptions);

    // Forward CORS and content-type headers
    res.setHeader("Access-Control-Allow-Origin", "*");
    const ct = backendRes.headers.get("content-type");
    if (ct) res.setHeader("Content-Type", ct);

    res.status(backendRes.status);

    const data = await backendRes.text();
    res.send(data);
  } catch (err) {
    console.error("[Proxy Error]", err.message);
    res.status(502).json({ detail: "Backend unreachable", error: err.message });
  }
}
