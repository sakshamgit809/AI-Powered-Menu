import { useState } from "react";
import { generateDetails } from "./api";
import "./styles.css";

export default function App() {
  const [item, setItem] = useState("");
  const [model, setModel] = useState("gpt-4");
  const [mode, setMode] = useState("mock"); // "mock", "openai", "serpapi"
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  function sanitizeClient(s) {
    const trimmed = s.trim();
    if (trimmed.length < 2 || trimmed.length > 120) return null;
    // deny angle brackets to avoid accidental HTML injection
    if (/[<>]/.test(trimmed)) return null;
    return trimmed;
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setData(null);
    const clean = sanitizeClient(item);
    if (!clean) {
      setErr("Please enter a valid item name (2–120 chars, no < >).");
      return;
    }
    setLoading(true);
    try {
      const res = await generateDetails(clean, model, mode);
      setData(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  function copy(text) {
    navigator.clipboard.writeText(text);
  }

  return (
    <div className="container">
      <h1>AI-Powered Menu Intelligence</h1>
      <p className="footer">
        Generate a short menu description (≤30 words) and one upsell combo.
      </p>

      <form onSubmit={onSubmit} className="card" style={{ marginTop: 12 }}>
        <div className="row">
          <div>
            <label>Food item</label>
            <input
              type="text"
              placeholder='e.g., "Paneer Tikka Pizza"'
              value={item}
              onChange={(e) => setItem(e.target.value)}
            />
          </div>

          <div>
            <label>Model</label>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="gpt-3.5">GPT-3.5</option>
              <option value="gpt-4">GPT-4</option>
            </select>
          </div>

          <div>
            <label>Mode</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="mock">Mock (no API key)</option>
              <option value="openai">OpenAI</option>
              <option value="serpapi">Serp API</option>
            </select>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? "Generating..." : "Generate"}
          </button>
        </div>

        {err && <div className="error">{err}</div>}
      </form>

      {data && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <div className="badge">{data.model}</div>
            <div className="badge">{data.meta?.wordCount ?? 0} words</div>
          </div>
          <h3 style={{ marginTop: 8 }}>{data.itemName}</h3>

          <p className="result" style={{ marginTop: 8 }}>
            {data.description}
          </p>
          <p className="result" style={{ marginTop: 6, fontWeight: 600 }}>
            {data.upsell}
          </p>

          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={() => copy(data.description)}>Copy Description</button>
            <button onClick={() => copy(data.upsell)}>Copy Upsell</button>
          </div>
        </div>
      )}

      <div className="footer">
        Tip: Use <b>Mock</b> mode to run without an API key. Switch to{" "}
        <b>Serp API</b> once you set <code>SERP_API_KEY</code> on the backend.
      </div>
    </div>
  );
}
