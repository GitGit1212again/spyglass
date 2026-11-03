// Talks to server.py. Every call returns parsed JSON or throws an Error with the server's message.

async function handle(res) {
  let data = null;
  try { data = await res.json(); } catch { /* not json */ }
  if (!res.ok) throw new Error((data && data.error) || `Server said ${res.status}`);
  return data;
}

export async function get(path) {
  return handle(await fetch(path, { cache: "no-store" }));
}

export async function post(path, body) {
  return handle(await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  }));
}

export async function upload(file, caseName) {
  const qs = new URLSearchParams({ case: caseName, name: file.name });
  return handle(await fetch(`/api/upload?${qs}`, { method: "POST", body: file }));
}
