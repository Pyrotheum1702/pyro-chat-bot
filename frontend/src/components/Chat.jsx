import { useEffect, useRef, useState } from "react";

export default function Chat({ messages, streaming, onSend }) {
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
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty">
            Hi! Ask me anything about Pyro — his background, projects, or skills.
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
          placeholder="Ask me anything…  (Enter to send, Shift+Enter for newline)"
          rows={2}
        />
        <button type="submit" disabled={streaming || !draft.trim()}>
          {streaming ? "…" : "Send"}
        </button>
      </form>
    </main>
  );
}
