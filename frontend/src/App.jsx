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

    // Optimistically add the user message + an empty assistant placeholder.
    setMessages((prev) => [
      ...prev,
      { role: "user", content: trimmed },
      { role: "assistant", content: "", sources: [] },
    ]);
    setStreaming(true);
    const startingNew = convId == null;

    await api.streamChat(
      { message: trimmed, conversationId: convId },
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
      <Chat messages={messages} streaming={streaming} onSend={handleSend} />
    </div>
  );
}

// Replace fields on the last (streaming assistant) message.
function patchLast(prev, patch) {
  const next = prev.slice();
  next[next.length - 1] = { ...next[next.length - 1], ...patch };
  return next;
}
