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
        setConfigForm({
          api_base: res.config.api_base || '',
          api_key: res.config.api_key || '',
          model: res.config.model || '',
        });
      }
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message with streaming
  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || streaming) return;

    const userMsg = { role: 'user', content: text, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setStreaming(true);

    // Create assistant placeholder
    const assistantId = Date.now() + 1;
    setMessages(prev => [...prev, { role: 'assistant', content: '', id: assistantId, tool_calls: [] }]);

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, conversation_id: conversationId }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const contentType = resp.headers.get('content-type') || '';

      if (contentType.includes('text/event-stream') || contentType.includes('text/plain')) {
        // SSE streaming
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith(':')) continue;
            if (trimmed.startsWith('data:')) {
              const data = trimmed.slice(5).trim();
              if (data === '[DONE]') continue;
              try {
                const parsed = JSON.parse(data);
                handleStreamChunk(parsed, assistantId);
              } catch {
                // Plain text chunk
                setMessages(prev => prev.map(m =>
                  m.id === assistantId ? { ...m, content: m.content + data } : m
                ));
              }
            } else {
              // Plain text line
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + trimmed + '\n' } : m
              ));
            }
          }
        }
      } else {
        // JSON response (non-streaming)
        const res = await resp.json();
        if (res.status === 'error') throw new Error(res.message || '对话失败');
        const content = res.reply || res.message || '';
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content } : m
        ));
        if (res.tool_calls) {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, tool_calls: res.tool_calls } : m
          ));
        }
      }
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: `[错误] ${e.message}` } : m
      ));
      toast(e.message, 'error');
    } finally {
      setStreaming(false);
    }
  }, [input, streaming, conversationId, toast]);

  function handleStreamChunk(parsed, assistantId) {
    if (parsed.content) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: m.content + parsed.content } : m
      ));
    }
    if (parsed.tool_calls) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, tool_calls: parsed.tool_calls } : m
      ));
    }
    if (parsed.reply) {
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: parsed.reply } : m
      ));
    }
  }

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
                } : msg.role === 'system' ? {
                  background: 'var(--bg-tertiary)', color: 'var(--text-secondary)',
                  fontStyle: 'italic',
                } : {
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  borderBottomLeftRadius: 4,
                }),
              }}>
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
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content || (streaming && msg.role === 'assistant' ? '' : '')}</div>
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {streaming && messages[messages.length - 1]?.role === 'assistant' && !messages[messages.length - 1]?.content && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div style={{
                padding: '10px 16px', borderRadius: 'var(--radius-lg)', borderBottomLeftRadius: 4,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                display: 'flex', gap: 4, alignItems: 'center',
              }}>
                <span className="typing-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)', animation: 'float 1.4s ease-in-out infinite' }} />
                <span className="typing-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)', animation: 'float 1.4s ease-in-out 0.2s infinite' }} />
                <span className="typing-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-tertiary)', animation: 'float 1.4s ease-in-out 0.4s infinite' }} />
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
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 'var(--space-md)' }}>AI 配置</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
            <div className="form-group">
              <label>API 地址</label>
              <input
                value={configForm.api_base}
                onChange={e => setConfigForm(f => ({ ...f, api_base: e.target.value }))}
                placeholder="https://api.openai.com/v1"
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
                placeholder="gpt-4o / glm-4"
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

      {/* Config toggle button (when panel is hidden) */}
      {!showConfig && (
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => setShowConfig(true)}
          style={{
            position: 'absolute', top: 'var(--space-sm)', right: 'var(--space-sm)',
            zIndex: 10,
          }}
          title="AI 配置"
        >
          ⚙️
        </button>
      )}

      {/* Config panel close */}
      {showConfig && (
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => setShowConfig(false)}
          style={{
            position: 'absolute', top: 'var(--space-sm)', right: 'var(--space-sm)',
            zIndex: 10,
          }}
          title="关闭配置"
        >
          ✕
        </button>
      )}
    </div>
  );
}
