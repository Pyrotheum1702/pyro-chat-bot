export default function Sidebar({ conversations, activeId, onSelect, onNew }) {
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
    </aside>
  );
}
