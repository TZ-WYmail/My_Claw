export default function AiChatViewerModal({ viewerModal, setViewerModal }) {
  if (!viewerModal.open) return null;

  const closeModal = () => setViewerModal({ open: false, type: 'text', title: '', content: '' });

  return (
    <div className="modal-overlay" onClick={closeModal}>
      <div className="modal ai-chat-modal" onClick={(event) => event.stopPropagation()}>
        <div className="card-header ai-chat-modal-header">
          <h3>{viewerModal.title}</h3>
          <button className="btn btn-sm btn-ghost" onClick={closeModal}>
            关闭
          </button>
        </div>
        {viewerModal.type === 'table' ? (
          <div className="markdown-body" dangerouslySetInnerHTML={{ __html: viewerModal.content }} />
        ) : (
          <pre className="ai-chat-modal-pre">
            <code>{viewerModal.content}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
