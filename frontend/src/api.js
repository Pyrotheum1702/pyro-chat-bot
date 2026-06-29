// API client. Same-origin in production; Vite proxies /api -> :8017 in dev.
const BASE = "";

async function asJson(res) {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function getConversations() {
  return asJson(await fetch(`${BASE}/api/conversations`));
}

export async function getConversation(id) {
  return asJson(await fetch(`${BASE}/api/conversations/${id}`));
}

export async function getDocuments() {
  return asJson(await fetch(`${BASE}/api/documents`));
}

export async function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  return asJson(await fetch(`${BASE}/api/documents`, { method: "POST", body: form }));
}

// Streams the chat response, parsing the SSE events the backend emits.
// handlers: { onStart, onSources, onToken, onError, onDone }
export async function streamChat({ message, conversationId, path = "/api/chat" }, handlers) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
    });
  } catch (e) {
    handlers.onError?.(e.message);
    handlers.onDone?.();
    return;
  }

  if (!res.ok || !res.body) {
    handlers.onError?.(`HTTP ${res.status}`);
    handlers.onDone?.();
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line.
      let sep;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const dataLine = block.split("\n").find((l) => l.startsWith("data:"));
        if (!dataLine) continue;
        const payload = dataLine.slice(5).trim();
        if (!payload) continue;

        let ev;
        try {
          ev = JSON.parse(payload);
        } catch {
          continue;
        }
        if (ev.type === "start") handlers.onStart?.(ev);
        else if (ev.type === "sources") handlers.onSources?.(ev.sources || []);
        else if (ev.type === "token") handlers.onToken?.(ev.value);
        else if (ev.type === "tool") handlers.onTool?.(ev);
        else if (ev.type === "tool_result") handlers.onToolResult?.(ev);
        else if (ev.type === "error") handlers.onError?.(ev.message);
        // "done" is handled by the finally block below
      }
    }
  } finally {
    handlers.onDone?.();
  }
}
