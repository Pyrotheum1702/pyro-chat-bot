export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  documents,
  onUpload,
  uploading,
}) {
  return (
    <aside className="sidebar">
      <button className="new-chat" onClick={onNew}>
        + New chat
      </button>

      <div className="section-title">Conversations</div>
      <ul className="list">
        {conversations.length === 0 && <li className="muted">No conversations yet</li>}
        {conversations.map((c) => (
          <li key={c.id}>
            <button
              className={"conv" + (c.id === activeId ? " active" : "")}
              onClick={() => onSelect(c.id)}
              title={c.title}
            >
              {c.title}
            </button>
          </li>
        ))}
      </ul>

      <div className="section-title">Documents</div>
      <label className={"upload" + (uploading ? " disabled" : "")}>
        {uploading ? "Uploading…" : "Upload .pdf / .txt / .md"}
        <input
          type="file"
          accept=".pdf,.txt,.md"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files && e.target.files[0];
            if (file) onUpload(file);
            e.target.value = ""; // allow re-uploading the same filename
          }}
        />
      </label>
      <ul className="list">
        {documents.length === 0 && <li className="muted">No documents yet</li>}
        {documents.map((d) => (
          <li key={d.id} className="doc">
            <span className="doc-name">{d.filename}</span>
            <span className="muted">{d.chunks} chunks</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
