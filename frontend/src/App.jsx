import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import Chat from "./components/Chat.jsx";
import * as api from "./api.js";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [convId, setConvId] = useState(null); // null => unsaved new chat
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [mode, setMode] = useState("chat"); // "chat" (RAG) | "agent" (tools)

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.getConversations());
    } catch {
      /* ignore */
    }
  }, []);

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await api.getDocuments());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refreshConversations();
    refreshDocuments();
  }, [refreshConversations, refreshDocuments]);

  async function selectConversation(id) {
    if (streaming) return;
    const detail = await api.getConversation(id);
    setConvId(id);
    setMessages(detail.messages.map((m) => ({ role: m.role, content: m.content })));
  }

  function newChat() {
    if (streaming) return;
    setConvId(null);
    setMessages([]);
  }

  async function handleUpload(file) {
    setUploading(true);
    try {
      await api.uploadDocument(file);
      await refreshDocuments();
    } catch (e) {
      alert("Upload failed: " + e.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleSend(text) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "", sources: [], tools: [] },
    ]);
    setStreaming(true);
    const startingNew = convId == null;

    await api.streamChat(
      {
        message: trimmed,
        conversationId: convId,
        path: mode === "agent" ? "/api/agent" : "/api/chat",
      },
      {
        onStart: (ev) => {
          if (startingNew) setConvId(ev.conversation_id);
        },
        onSources: (sources) => setMessages((prev) => patchLast(prev, { sources })),
        onToken: (tok) =>
          setMessages((prev) => {
            const next = prev.slice();
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: last.content + tok };
            return next;
          }),
        onTool: (ev) =>
          setMessages((prev) => {
            const next = prev.slice();
            const last = next[next.length - 1];
            const tools = [...(last.tools || []), { name: ev.name, input: ev.input, output: null }];
            next[next.length - 1] = { ...last, tools };
            return next;
          }),
        onToolResult: (ev) =>
          setMessages((prev) => {
            const next = prev.slice();
            const last = next[next.length - 1];
            const tools = (last.tools || []).slice();
            // attach the result to the most recent pending call of this tool
            for (let i = tools.length - 1; i >= 0; i--) {
              if (tools[i].name === ev.name && tools[i].output == null) {
                tools[i] = { ...tools[i], output: ev.output };
                break;
              }
            }
            next[next.length - 1] = { ...last, tools };
            return next;
          }),
        onError: (msg) =>
          setMessages((prev) => {
            const next = prev.slice();
            const last = next[next.length - 1];
            next[next.length - 1] = {
              ...last,
              content: last.content + `\n\n_[error: ${msg}]_`,
            };
            return next;
          }),
        onDone: () => {
          setStreaming(false);
          refreshConversations();
          refreshDocuments(); // agent may have ingested a URL
        },
      }
    );
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        activeId={convId}
        onSelect={selectConversation}
        onNew={newChat}
        documents={documents}
        onUpload={handleUpload}
        uploading={uploading}
      />
      <Chat
        messages={messages}
        streaming={streaming}
        onSend={handleSend}
        mode={mode}
        onModeChange={setMode}
      />
    </div>
  );
}

function patchLast(prev, patch) {
  const next = prev.slice();
  next[next.length - 1] = { ...next[next.length - 1], ...patch };
  return next;
}
