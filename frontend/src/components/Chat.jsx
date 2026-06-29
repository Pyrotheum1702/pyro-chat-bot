import { useEffect, useRef, useState } from "react";

export default function Chat({ messages, streaming, onSend, mode, onModeChange }) {
  const [draft, setDraft] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function submit(e) {
    e.preventDefault();
    if (!draft.trim() || streaming) return;
    onSend(draft);
    setDraft("");
  }

  return (
    <main className="chat">
      <header className="chat-header">
        <div className="mode-toggle">
          {["chat", "agent"].map((m) => (
            <button
              key={m}
              className={"mode" + (mode === m ? " active" : "")}
              onClick={() => !streaming && onModeChange(m)}
              disabled={streaming}
              title={m === "chat" ? "RAG over your documents" : "Tool-using agent"}
            >
              {m === "chat" ? "Chat (RAG)" : "Agent (tools)"}
            </button>
          ))}
        </div>
      </header>

      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            {mode === "agent"
              ? "Agent mode: I can search your docs, search the web, do math, and ingest URLs."
              : "Upload a document in the sidebar, then ask a question about it."}
          </div>
        )}

        {messages.map((m, i) => {
          const isLast = i === messages.length - 1;
          return (
            <div key={i} className={"msg " + m.role}>
              {m.role === "assistant" && m.tools && m.tools.length > 0 && (
                <div className="tools">
                  {m.tools.map((t, k) => (
                    <details key={k} className="tool">
                      <summary>
                        🔧 {t.name}
                        {t.output == null ? " …" : ""}
                      </summary>
                      <div className="tool-body">
                        <div className="muted">input: {JSON.stringify(t.input)}</div>
                        {t.output != null && <div className="snippet">{t.output}</div>}
                      </div>
                    </details>
                  ))}
                </div>
              )}

              <div className="bubble">
                {m.content || (streaming && isLast ? "…" : "")}
              </div>

              {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                <details className="sources">
                  <summary>{m.sources.length} source(s)</summary>
                  <ul>
                    {m.sources.map((s, j) => (
                      <li key={j}>
                        <strong>
                          {s.source}
                          {s.page != null ? ` · p.${s.page}` : ""}
                        </strong>
                        <div className="snippet">{s.snippet}</div>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={submit}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) submit(e);
          }}
          placeholder={
            mode === "agent"
              ? "Ask the agent…  (it can use tools)"
              : "Ask a question…  (Enter to send, Shift+Enter for newline)"
          }
          rows={2}
        />
        <button type="submit" disabled={streaming || !draft.trim()}>
          {streaming ? "…" : "Send"}
        </button>
      </form>
    </main>
  );
}
