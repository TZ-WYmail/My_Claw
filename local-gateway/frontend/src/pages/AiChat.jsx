import { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';

export default function AiChat() {
  const toast = useToast();
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [currentModel, setCurrentModel] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [conversationId] = useState('default');

  // Config state
  const [config, setConfig] = useState(null);
  const [configForm, setConfigForm] = useState({ api_base: '', api_key: '', model: '' });
  const [showConfig, setShowConfig] = useState(false);
  const [testing, setTesting] = useState(false);

  // Fetch config
  const fetchConfig = useCallback(async () => {
    try {
      const res = await apiGet('/api/chat/config');
      if (res.status === 'success' && res.config) {
        setConfig(res.config);
        setCurrentModel(res.config.model || '');
        setConfigForm({
          api_base: res.config.api_base || '',
          api_key: res.config.api_key_masked || res.config.api_key || '',
          model: res.config.model || '',
        });
      }
    } catch { /* silent */ }
  }, []);

  // Load conversation history
  const loadHistory = useCallback(async () => {
    try {
      const res = await apiGet(`/api/chat/history/${conversationId}`);
      if (res.status === 'success' && res.messages?.length > 0) {
        setMessages(res.messages.map((m, i) => ({
          id: m.id || i,
          role: m.role,
          content: m.content || '',
          thinking: m.thinking || '',
          model: m.model || '',
          timestamp: m.timestamp,
        })));
      }
    } catch { /* silent */ }
  }, [conversationId]);

  useEffect(() => { fetchConfig(); loadHistory(); }, [fetchConfig, loadHistory]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message with SSE streaming
  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg = { role: 'user', content: text, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setStreaming(true);
    setIsThinking(false);

    const assistantId = Date.now() + 1;
    const assistantMsg = { role: 'assistant', content: '', thinking: '', model: '', id: assistantId, tool_calls: [] };
    setMessages(prev => [...prev, assistantMsg]);

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE: look for "event: xxx\ndata: xxx\n\n"
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const eventMatch = part.match(/^event:\s*(.+)$/m);
          const dataMatch = part.match(/^data:\s*(.+)$/m);
          if (!eventMatch || !dataMatch) continue;

          const event = eventMatch[1].trim();
          let data;
          try { data = JSON.parse(dataMatch[1]); } catch { continue; }

          switch (event) {
            case 'model':
              setCurrentModel(data.model || '');
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, model: data.model || '' } : m
              ));
              break;

            case 'thinking':
              setIsThinking(true);
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, thinking: m.thinking + (data.content || '') } : m
              ));
              break;

            case 'content':
              setIsThinking(false);
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + (data.content || '') } : m
              ));
              break;

            case 'tool_call':
              setMessages(prev => prev.map(m =>
                m.id === assistantId
                  ? { ...m, tool_calls: [...m.tool_calls, { function: { name: data.name, arguments: data.arguments } }] }
                  : m
              ));
              break;

            case 'tool_result':
              // Tool result shown inline, no separate UI needed
              break;

            case 'done':
              setIsThinking(false);
              break;

            case 'error':
              setIsThinking(false);
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: `[错误] ${data.message || '未知错误'}` } : m
              ));
              toast(data.message || '对话失败', 'error');
              break;
          }
        }
      }
    } catch (e) {
      setIsThinking(false);
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: `[错误] ${e.message}` } : m
      ));
      toast(e.message, 'error');
    } finally {
      setStreaming(false);
    }
  }, [input, streaming, conversationId, toast]);

  // Save config
  const saveConfig = async () => {
    try {
      const res = await apiPost('/api/chat/config', {
        api_base: configForm.api_base.trim(),
        api_key: configForm.api_key.trim(),
        model: configForm.model.trim(),
      });
      if (res.status === 'error') throw new Error(res.message);
      toast('配置已保存', 'success');
      setConfig(res.config || configForm);
      setCurrentModel(configForm.model);
      fetchConfig();
    } catch (e) { toast(e.message, 'error'); }
  };

  // Test connection
  const testConnection = async () => {
    setTesting(true);
    try {
      const res = await apiPost('/api/chat/test', {
        api_base: configForm.api_base.trim(),
        api_key: configForm.api_key.trim(),
        model: configForm.model.trim(),
      });
      if (res.status === 'success') {
        toast('连接成功: ' + (res.test_reply || res.reply || 'OK'), 'success');
      } else {
        toast('连接失败: ' + (res.message || '未知错误'), 'error');
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setTesting(false); }
  };

  // Clear conversation
  const clearChat = async () => {
    try {
      await apiPost('/api/chat/clear', { conversation_id: conversationId });
      setMessages([]);
      toast('对话已清除', 'success');
    } catch (e) { toast(e.message, 'error'); }
  };

  // Handle Enter
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ display: 'flex', height: '100%', minHeight: 0 }}>
      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header with model info */}
        <div style={{
          padding: '8px var(--space-md)', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center',
          gap: 'var(--space-sm)', fontSize: '0.82rem',
        }}>
          <span style={{ fontWeight: 600 }}>AI 对话</span>
          {currentModel && (
            <span className="badge badge-pending" style={{ fontSize: '0.72rem' }}>
              {currentModel}
            </span>
          )}
          {isThinking && (
            <span style={{ color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--warning)', animation: 'float 1s ease-in-out infinite' }} />
              思考中...
            </span>
          )}
          <div style={{ flex: 1 }} />
          <button className="btn btn-sm btn-ghost" onClick={() => setShowConfig(s => !s)} title="AI 配置">
            ⚙️
          </button>
        </div>

        {/* Messages */}
        <div style={{
          flex: 1, overflowY: 'auto', padding: 'var(--space-md)',
          display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)',
        }}>
          {messages.length === 0 && (
            <div className="empty-state" style={{ flex: 1 }}>
              <div className="empty-state-icon">🤖</div>
              <div className="empty-state-text">开始和 AI 对话</div>
              <div className="empty-state-hint">输入问题，AI 会调用本地工具帮你完成任务</div>
            </div>
          )}

          {messages.map(msg => (
            <div key={msg.id} style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}>
              <div style={{
                maxWidth: '75%', padding: '10px 16px', borderRadius: 'var(--radius-lg)',
                fontSize: '0.9rem', lineHeight: 1.6, wordBreak: 'break-word',
                ...(msg.role === 'user' ? {
                  background: 'var(--accent)', color: '#fff',
                  borderBottomRightRadius: 4,
                } : {
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  borderBottomLeftRadius: 4,
                }),
              }}>
                {/* Model badge for assistant messages */}
                {msg.role === 'assistant' && msg.model && (
                  <div style={{ marginBottom: 6, fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>
                    {msg.model}
                  </div>
                )}

                {/* Thinking block */}
                {msg.thinking && (
                  <details style={{ marginBottom: 8 }}>
                    <summary style={{
                      fontSize: '0.78rem', color: 'var(--warning)', cursor: 'pointer',
                      userSelect: 'none', padding: '2px 0',
                    }}>
                      💭 思考过程 {isThinking && msg.id === messages[messages.length - 1]?.id && '...'}
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

                {/* Tool calls display */}
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

                {/* Message content */}
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              </div>
            </div>
          ))}

          {/* Typing indicator when no content yet */}
          {streaming && messages.length > 0 && messages[messages.length - 1]?.role === 'assistant' &&
           !messages[messages.length - 1]?.content && !messages[messages.length - 1]?.thinking && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div style={{
                padding: '10px 16px', borderRadius: 'var(--radius-lg)', borderBottomLeftRadius: 4,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                display: 'flex', gap: 4, alignItems: 'center',
              }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)', animation: 'float 1.4s ease-in-out infinite' }} />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)', animation: 'float 1.4s ease-in-out 0.2s infinite' }} />
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)', animation: 'float 1.4s ease-in-out 0.4s infinite' }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div style={{
          padding: 'var(--space-md)', borderTop: '1px solid var(--border)',
          background: 'var(--bg-card)',
        }}>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'flex-end' }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
              rows={1}
              style={{
                flex: 1, resize: 'none', minHeight: 40, maxHeight: 120,
                padding: '10px 12px',
              }}
              disabled={streaming}
            />
            <button
              className="btn btn-primary"
              onClick={sendMessage}
              disabled={streaming || !input.trim()}
              style={{ height: 40, flexShrink: 0 }}
            >
              {streaming ? '...' : '发送'}
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel: Config */}
      {showConfig && (
        <div style={{
          width: 300, borderLeft: '1px solid var(--border)', background: 'var(--bg-secondary)',
          padding: 'var(--space-lg)', overflowY: 'auto', flexShrink: 0,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-md)' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>AI 配置</h3>
            <button className="btn btn-sm btn-ghost" onClick={() => setShowConfig(false)}>✕</button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            <div className="form-group">
              <label>API 地址</label>
              <input
                value={configForm.api_base}
                onChange={e => setConfigForm(f => ({ ...f, api_base: e.target.value }))}
                placeholder="https://api.deepseek.com"
              />
            </div>
            <div className="form-group">
              <label>API Key</label>
              <input
                type="password"
                value={configForm.api_key}
                onChange={e => setConfigForm(f => ({ ...f, api_key: e.target.value }))}
                placeholder="sk-..."
              />
            </div>
            <div className="form-group">
              <label>模型</label>
              <input
                value={configForm.model}
                onChange={e => setConfigForm(f => ({ ...f, model: e.target.value }))}
                placeholder="deepseek-v4-pro"
              />
            </div>

            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={saveConfig}>保存</button>
              <button className="btn" style={{ flex: 1 }} onClick={testConnection} disabled={testing}>
                {testing ? '测试中...' : '测试连接'}
              </button>
            </div>
          </div>

          <div style={{ marginTop: 'var(--space-xl)', borderTop: '1px solid var(--border)', paddingTop: 'var(--space-md)' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 'var(--space-md)' }}>对话操作</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              <button className="btn btn-danger" onClick={clearChat}>清除对话</button>
            </div>
          </div>

          {config && (
            <div style={{ marginTop: 'var(--space-xl)', fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
              <div>当前模型: {config.model || '-'}</div>
              <div>API: {config.api_base || '-'}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
