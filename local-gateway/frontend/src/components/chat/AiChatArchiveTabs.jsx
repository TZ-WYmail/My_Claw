export default function AiChatArchiveTabs({
  conversations,
  activeConvId,
  createConversation,
  switchConversation,
  deleteConversation,
  expanded,
  setExpanded,
}) {
  const trimTitle = (title) => {
    const value = (title || '新对话').trim();
    return Array.from(value).slice(0, 6).join('');
  };

  return (
    <aside
      className={`ai-archive-tabs ${expanded ? 'expanded' : ''}`}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      <div className="ai-archive-head">
        <div>
          <div className="section-kicker">Archive</div>
          <div className="ai-archive-title">对话档案夹</div>
        </div>
        <div className="ai-archive-head-actions">
          <button
            className="ai-archive-peek"
            onClick={() => setExpanded((value) => !value)}
            aria-label={expanded ? '收起档案夹' : '展开档案夹'}
          >
            {expanded ? '收起' : '展开'}
          </button>
          <button className="btn btn-primary" onClick={createConversation}>+ 新回合</button>
        </div>
      </div>
      <div className="ai-archive-copy">
        保留不同任务线索，像切换任务存档一样回看策略。
      </div>
      <div className="ai-archive-list ai-archive-tab-list">
        {conversations.map((conv, index) => (
          <div
            key={conv.id}
            className={`ai-archive-item ai-archive-tab ${conv.id === activeConvId ? 'active' : ''}`}
            onClick={() => switchConversation(conv.id)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                switchConversation(conv.id);
              }
            }}
            role="button"
            tabIndex={0}
            style={{ '--archive-index': index }}
          >
            <div className="ai-archive-item-main">
              <span className="ai-archive-item-index">#{String(index + 1).padStart(2, '0')}</span>
              <span className="ai-archive-item-title">{trimTitle(conv.title)}</span>
            </div>
            <button
              className="ai-archive-delete"
              onClick={(event) => deleteConversation(conv.id, event)}
              aria-label={`删除对话 ${conv.title || index + 1}`}
            >
              归档
            </button>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="ai-archive-empty">暂无存档，先开启一条新战线。</div>
        )}
      </div>
    </aside>
  );
}
