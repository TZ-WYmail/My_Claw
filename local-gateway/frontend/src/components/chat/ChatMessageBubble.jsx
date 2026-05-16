import AssistantMarkdown from './AssistantMarkdown';

export default function ChatMessageBubble({ msg, isThinking, maxWidth = '75%' }) {
  return (
    <div style={{
      maxWidth, padding: '10px 16px', borderRadius: 'var(--radius-lg)',
      fontSize: '0.9rem', lineHeight: 1.6, wordBreak: 'break-word',
      ...(msg.role === 'user' ? {
        background: 'var(--accent)', color: '#fff',
        borderBottomRightRadius: 4,
      } : {
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderBottomLeftRadius: 4,
      }),
    }}>
      {msg.role === 'assistant' && msg.model && (
        <div style={{ marginBottom: 6, fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
          {msg.model}
        </div>
      )}

      {msg.thinking && (
        <details style={{ marginBottom: 8 }}>
          <summary style={{
            fontSize: '0.78rem', color: 'var(--warning)', cursor: 'pointer',
            userSelect: 'none', padding: '2px 0',
          }}>
            💭 思考过程 {isThinking && '...'}
          </summary>
          <div style={{
            fontSize: '0.82rem', color: 'var(--text-tertiary)', lineHeight: 1.5,
            padding: '8px 10px', marginTop: 4,
            background: 'rgba(255,159,10,0.06)', borderRadius: 'var(--radius-sm)',
            border: '1px solid rgba(255,159,10,0.12)',
            whiteSpace: 'pre-wrap', maxHeight: 300, overflowY: 'auto',
          }}>
            {msg.thinking}
          </div>
        </details>
      )}

      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {msg.tool_calls.map((tc, i) => (
            <div key={i} style={{
              fontSize: '0.78rem', padding: '4px 8px', marginBottom: 4,
              borderRadius: 'var(--radius-sm)', background: 'rgba(10,132,255,0.08)',
              border: '1px solid rgba(10,132,255,0.15)', color: 'var(--accent)',
            }}>
              🔧 {tc.function?.name || tc.name || 'tool'}
              {tc.function?.arguments && (
                <pre style={{ margin: '4px 0 0', fontSize: '0.7rem', color: 'var(--text-tertiary)', whiteSpace: 'pre-wrap' }}>
                  {typeof tc.function.arguments === 'string'
                    ? tc.function.arguments
                    : JSON.stringify(tc.function.arguments, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {msg.role === 'assistant' ? (
        <AssistantMarkdown content={msg.content} />
      ) : (
        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
      )}
    </div>
  );
}
