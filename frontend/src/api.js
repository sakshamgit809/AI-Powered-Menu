export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

async function http(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export function generateDetails(itemName, model = "gpt-4", mode = "mock") {
  return http(`${API_BASE}/generate-item-details/`, {
    method: "POST",
    body: JSON.stringify({ itemName, model, mode })
  });
}
