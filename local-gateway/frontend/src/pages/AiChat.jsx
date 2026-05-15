import { useState, useEffect, useCallback, useRef } from 'react';
import { apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import ChatMessageBubble from '../components/chat/ChatMessageBubble';

export default function AiChat() {
  const toast = useToast();
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const mermaidRenderTimerRef = useRef(null);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [currentModel, setCurrentModel] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState('default');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Config state
  const [config, setConfig] = useState(null);
  const [configForm, setConfigForm] = useState({ api_base: '', api_key: '', model: '' });
  const [showConfig, setShowConfig] = useState(false);
  const [testing, setTesting] = useState(false);
  const [planningText, setPlanningText] = useState('');
  const [planningPreview, setPlanningPreview] = useState(null);
  const [planningLoading, setPlanningLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState('balanced');
  const [interruptTaskName, setInterruptTaskName] = useState('');
  const [interruptTaskDueTime, setInterruptTaskDueTime] = useState('');
  const [replanResult, setReplanResult] = useState(null);
  const [acceptedSuggestions, setAcceptedSuggestions] = useState([]);
  const [reasonFilter, setReasonFilter] = useState('all');
  const [viewerModal, setViewerModal] = useState({ open: false, type: 'text', title: '', content: '' });

  const filteredSuggestions = (replanResult?.reordered_tasks || [])
    .filter(item => reasonFilter === 'all' || item.reason_type === reasonFilter)
    .sort((a, b) => {
      const aImpact = (a.impact_scope?.days || 0) * 100 + (a.impact_scope?.tasks || 0);
      const bImpact = (b.impact_scope?.days || 0) * 100 + (b.impact_scope?.tasks || 0);
      return bImpact - aImpact;
    });
  const mustChangeSuggestions = filteredSuggestions.filter(item => item.severity === 'must_change');
  const optionalSuggestions = filteredSuggestions.filter(item => item.severity !== 'must_change');
  const getActivePlanningView = useCallback((preview, variantId) => {
    if (!preview) return null;
    const activeVariantId = variantId || preview.selected_variant || 'balanced';
    const variantPlan = preview.variant_plans?.[activeVariantId];
    if (!variantPlan) return preview;
    return {
      ...preview,
      selected_variant: activeVariantId,
      daily_plan: variantPlan.daily_plan || {},
      daily_timeline: variantPlan.daily_timeline || [],
      conflicts: variantPlan.conflicts || [],
      overload_days: variantPlan.overload_days || [],
      infeasible_tasks: variantPlan.infeasible_tasks || [],
    };
  }, []);

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

  // Fetch conversations
  const fetchConversations = useCallback(async () => {
    try {
      const res = await apiGet('/api/chat/conversations');
      if (res.status === 'success') {
        setConversations(res.conversations || []);
      }
    } catch { /* silent */ }
  }, []);

  // Load conversation history
  const loadHistory = useCallback(async () => {
    try {
      const res = await apiGet(`/api/chat/history/${activeConvId}`);
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
  }, [activeConvId]);

  useEffect(() => { fetchConfig(); fetchConversations(); loadHistory(); }, [fetchConfig, fetchConversations, loadHistory]);

  // New conversation
  const createConversation = async () => {
    try {
      const res = await apiPost('/api/chat/conversations', {});
      if (res.status === 'success') {
        setActiveConvId(res.conversation_id);
        setMessages([]);
        fetchConversations();
      }
    } catch (e) { toast(e.message, 'error'); }
  };

  // Switch conversation
  const switchConversation = async (convId) => {
    setActiveConvId(convId);
    try {
      const res = await apiGet(`/api/chat/history/${convId}`);
      if (res.status === 'success' && res.messages?.length > 0) {
        setMessages(res.messages.map((m, i) => ({
          id: m.id || i, role: m.role, content: m.content || '',
          thinking: m.thinking || '', model: m.model || '', timestamp: m.timestamp,
        })));
      } else {
        setMessages([]);
      }
    } catch { setMessages([]); }
  };

  // Delete conversation
  const deleteConversation = async (convId, e) => {
    e.stopPropagation();
    if (!confirm('确认删除此对话？')) return;
    try {
      const res = await fetch(`/api/chat/conversations/${convId}`, { method: 'DELETE' }).then(r => r.json());
      if (res.status !== 'success') {
        throw new Error(res.message || '删除失败');
      }
      toast('对话已删除', 'success');
      if (activeConvId === convId) {
        const remaining = conversations.filter(c => c.id !== convId);
        if (remaining.length > 0) {
          switchConversation(remaining[0].id);
        } else {
          createConversation();
        }
      }
      fetchConversations();
    } catch (e) { toast(e.message, 'error'); }
  };

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const handleCopy = async (event) => {
      const target = event.target;
      if (!target || !target.classList?.contains('markdown-code-copy')) return;
      const code = decodeURIComponent(target.getAttribute('data-code') || '');
      try {
        await navigator.clipboard.writeText(code);
        toast('代码已复制', 'success');
      } catch {
        toast('复制失败', 'error');
      }
    };

    document.addEventListener('click', handleCopy);
    return () => document.removeEventListener('click', handleCopy);
  }, [toast]);

  useEffect(() => {
    const handleExpand = (event) => {
      const target = event.target;
      if (!target) return;

      if (target.classList?.contains('markdown-code-expand')) {
        const code = decodeURIComponent(target.getAttribute('data-code') || '');
        const language = target.getAttribute('data-language') || 'code';
        setViewerModal({ open: true, type: 'code', title: `代码块 · ${language}`, content: code });
      }

      if (target.classList?.contains('markdown-table-expand')) {
        const tableHtml = decodeURIComponent(target.getAttribute('data-table') || '');
        setViewerModal({ open: true, type: 'table', title: '表格查看', content: tableHtml });
      }
    };

    document.addEventListener('click', handleExpand);
    return () => document.removeEventListener('click', handleExpand);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (mermaidRenderTimerRef.current) {
      clearTimeout(mermaidRenderTimerRef.current);
    }

    const renderMermaidBlocks = async () => {
      const blocks = document.querySelectorAll('.markdown-mermaid-source');
      if (!blocks.length) return;

      try {
        const mermaidModule = await import('mermaid');
        if (cancelled) return;
        const mermaid = mermaidModule.default || mermaidModule;
        mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default' });

        let index = 0;
        for (const block of blocks) {
          const source = decodeURIComponent(block.getAttribute('data-mermaid') || '');
          const target = block.parentElement?.querySelector('.markdown-mermaid-render');
          if (!source || !target) continue;
          if (target.getAttribute('data-rendered-source') === source) continue;
          try {
            const renderId = `mermaid-${Date.now()}-${index++}`;
            const { svg } = await mermaid.render(renderId, source);
            if (!cancelled) {
              target.innerHTML = svg;
              target.setAttribute('data-rendered-source', source);
            }
          } catch {
            if (!cancelled) target.innerHTML = '<div class="markdown-mermaid-note">Mermaid 渲染失败，已保留源码。</div>';
          }
        }
      } catch {
        // ignore, fallback to source-only display
      }
    };

    const latestAssistant = [...messages].reverse().find(item => item.role === 'assistant');
    const hasMermaidSource = latestAssistant?.content?.includes('```mermaid');
    if (!hasMermaidSource && !document.querySelector('.markdown-mermaid-source')) {
      return () => {
        cancelled = true;
        if (mermaidRenderTimerRef.current) {
          clearTimeout(mermaidRenderTimerRef.current);
        }
      };
    }

    mermaidRenderTimerRef.current = setTimeout(renderMermaidBlocks, 180);
    return () => {
      cancelled = true;
      if (mermaidRenderTimerRef.current) {
        clearTimeout(mermaidRenderTimerRef.current);
      }
    };
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
        body: JSON.stringify({ message: text, conversation_id: activeConvId }),
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
  }, [input, streaming, activeConvId, toast]);

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
      await fetch(`/api/chat/conversations/${activeConvId}`, { method: 'DELETE' }).then(r => r.json());
      setMessages([]);
      fetchConversations();
      toast('对话已删除', 'success');
    } catch (e) { toast(e.message, 'error'); }
  };

  const previewPlanning = async () => {
    if (!planningText.trim()) {
      toast('请输入任务列表', 'error');
      return;
    }
    setPlanningLoading(true);
    try {
      const tasks = planningText
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => {
          const [name, due, earliestStart, dependencies] = line.split('|').map(item => (item || '').trim());
          return {
            task_name: name,
            due_time: due || '',
            earliest_start: earliestStart || '',
            depends_on: dependencies ? dependencies.split(',').map(item => item.trim()).filter(Boolean) : [],
          };
        });
      const res = await apiPost('/api/ai/plan/preview', {
        tasks,
        constraints: { default_daily_hours: 6, weekend_daily_hours: 4, buffer_ratio: 0.2 },
      });
      if (res.status === 'error') throw new Error(res.message || '预览失败');
      setPlanningPreview(res);
      setSelectedVariant(res.variants?.[0]?.id || 'balanced');
      setInterruptTaskName('');
      setInterruptTaskDueTime('');
      setReplanResult(null);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setPlanningLoading(false);
    }
  };

  const confirmPlanning = async () => {
    if (!planningPreview?.preview_id) return;
    setPlanningLoading(true);
    try {
      const res = await apiPost('/api/ai/plan/confirm', {
        preview_id: planningPreview.preview_id,
        selected_variant: selectedVariant,
        user_adjustments: {},
      });
      if (res.status === 'error') throw new Error(res.message || '创建失败');
      toast(`已创建 ${res.success_count || 0} 项任务`, 'success');
      setPlanningPreview(null);
      setPlanningText('');
      setInterruptTaskName('');
      setInterruptTaskDueTime('');
      setReplanResult(null);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setPlanningLoading(false);
    }
  };

  const replanWithInterrupt = async () => {
    if (!planningText.trim()) {
      toast('请先输入基础任务列表', 'error');
      return;
    }
    if (!interruptTaskName.trim() || !interruptTaskDueTime.trim()) {
      toast('请填写突发任务名称和截止时间', 'error');
      return;
    }
    setPlanningLoading(true);
    try {
      const tasks = planningText
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => {
          const [name, due, earliestStart, dependencies] = line.split('|').map(item => (item || '').trim());
          return {
            task_name: name,
            due_time: due || '',
            earliest_start: earliestStart || '',
            depends_on: dependencies ? dependencies.split(',').map(item => item.trim()).filter(Boolean) : [],
          };
        });
      const res = await apiPost('/api/ai/plan/replan', {
        tasks,
        constraints: { default_daily_hours: 6, weekend_daily_hours: 4, buffer_ratio: 0.2 },
        interrupt_task: {
          task_name: interruptTaskName.trim(),
          due_time: interruptTaskDueTime.trim(),
        },
      });
      if (res.status === 'error') throw new Error(res.message || '重排失败');
      const suggested = res.suggested_plan || res.new_plan;
      setPlanningPreview(suggested);
      setSelectedVariant(suggested?.selected_variant || suggested?.variants?.[0]?.id || 'balanced');
      setReplanResult(res);
      setAcceptedSuggestions((res.reordered_tasks || []).map(item => item.task_name));
      toast(`已重排，建议后移 ${res.postpone_candidates?.length || 0} 项任务`, 'success');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setPlanningLoading(false);
    }
  };

  const rerunWithAcceptedSuggestions = async () => {
    if (!planningText.trim() || !replanResult) return;
    setPlanningLoading(true);
    try {
      const tasks = planningText
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => {
          const [name, due, earliestStart, dependencies] = line.split('|').map(item => (item || '').trim());
          return {
            task_name: name,
            due_time: due || '',
            earliest_start: earliestStart || '',
            depends_on: dependencies ? dependencies.split(',').map(item => item.trim()).filter(Boolean) : [],
          };
        });
      const res = await apiPost('/api/ai/plan/replan/accept', {
        tasks,
        constraints: { default_daily_hours: 6, weekend_daily_hours: 4, buffer_ratio: 0.2 },
        interrupt_task: interruptTaskName.trim() ? {
          task_name: interruptTaskName.trim(),
          due_time: interruptTaskDueTime.trim(),
        } : null,
        accepted_task_names: acceptedSuggestions,
      });
      if (res.status === 'error') throw new Error(res.message || '二次重排失败');
      setReplanResult(res);
      setPlanningPreview(res.suggested_plan || res.new_plan);
      setSelectedVariant(res.suggested_plan?.selected_variant || res.new_plan?.selected_variant || 'balanced');
      toast('已按选择建议生成新方案', 'success');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setPlanningLoading(false);
    }
  };

  const activePlanningView = getActivePlanningView(planningPreview, selectedVariant);

  // Handle Enter
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{ display: 'flex', height: '100%', minHeight: 0 }}>
      {/* Left Sidebar - Conversation List */}
      {sidebarOpen && (
        <div style={{
          width: 240, borderRight: '1px solid var(--border)',
          background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column',
          flexShrink: 0, overflow: 'hidden',
        }}>
          {/* New conversation button */}
          <div style={{ padding: 'var(--space-sm) var(--space-md)', borderBottom: '1px solid var(--border)' }}>
            <button className="btn btn-primary" style={{ width: '100%' }} onClick={createConversation}>
              + 新对话
            </button>
          </div>
          {/* Conversation list */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-xs)' }}>
            {conversations.map(conv => (
              <div
                key={conv.id}
                onClick={() => switchConversation(conv.id)}
                style={{
                  padding: '8px 12px', borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer', marginBottom: 2, position: 'relative',
                  background: conv.id === activeConvId ? 'rgba(10,132,255,0.1)' : 'transparent',
                  borderLeft: conv.id === activeConvId ? '3px solid var(--accent)' : '3px solid transparent',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  fontSize: '0.85rem',
                }}
                onMouseEnter={e => { if (conv.id !== activeConvId) e.currentTarget.style.background = 'var(--bg-tertiary)'; }}
                onMouseLeave={e => { if (conv.id !== activeConvId) e.currentTarget.style.background = 'transparent'; }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                  {conv.title || '新对话'}
                </span>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={(e) => deleteConversation(conv.id, e)}
                  style={{ padding: '0 4px', fontSize: '0.7rem', opacity: 0.5, minWidth: 20 }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Header with model info */}
        <div style={{
          padding: '8px var(--space-md)', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center',
          gap: 'var(--space-sm)', fontSize: '0.82rem',
        }}>
          <button className="btn btn-sm btn-ghost" onClick={() => setSidebarOpen(s => !s)} title="对话列表">
            ☰
          </button>
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
          <div className="card" style={{ marginBottom: 'var(--space-sm)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-sm)' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>AI 安排任务</h3>
              <span className="badge badge-pending">preview → confirm</span>
            </div>
            <textarea
              value={planningText}
              onChange={e => setPlanningText(e.target.value)}
              placeholder={`每行一个任务，格式：\n任务名 | 截止时间 | 最早开始时间(可选) | 依赖任务(可选,逗号分隔)\n例如：\n收集数据 | 2026-05-18 | 2026-05-16 |\n写周报 | 2026-05-19 | 2026-05-18 | 收集数据\n准备汇报 | 2026-05-20 | | 写周报`}
              rows={5}
              style={{ marginBottom: 'var(--space-sm)' }}
            />
              <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
                <button className="btn btn-primary" onClick={previewPlanning} disabled={planningLoading}>
                  {planningLoading ? '预览中...' : '预览安排'}
                </button>
                <button className="btn btn-ghost" onClick={() => setPlanningPreview(null)} disabled={!planningPreview}>
                清空预览
              </button>
            </div>
          </div>

          {planningPreview && (
            <div className="card" style={{ marginBottom: 'var(--space-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', marginBottom: 'var(--space-sm)' }}>
                <div>
                  <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 4 }}>预览结果</h3>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                    {activePlanningView?.explanation?.summary || planningPreview.explanation?.summary || '已生成结构化预览'}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(planningPreview.variants || []).map(variant => (
                    <button
                      key={variant.id}
                      className={`btn btn-sm ${selectedVariant === variant.id ? 'btn-primary' : 'btn-ghost'}`}
                      onClick={() => setSelectedVariant(variant.id)}
                      title={`风险:${variant.summary?.risk_level || '-'} / 过载日:${variant.summary?.overload_day_count || 0}`}
                    >
                      {variant.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 'var(--space-sm)', fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                <span>当前方案：{selectedVariant}</span>
                <span>风险：{planningPreview.variants?.find(v => v.id === selectedVariant)?.summary?.risk_level || '-'}</span>
                <span>过载日：{planningPreview.variants?.find(v => v.id === selectedVariant)?.summary?.overload_day_count || 0}</span>
                <span>冲突：{planningPreview.variants?.find(v => v.id === selectedVariant)?.summary?.conflict_count || 0}</span>
                <span>深度工作日：{planningPreview.variants?.find(v => v.id === selectedVariant)?.summary?.deep_work_days || 0}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 'var(--space-sm)' }}>
                {(activePlanningView?.conflicts || []).map((item, index) => (
                  <div key={index} style={{ fontSize: '0.8rem', color: 'var(--warning)' }}>⚠️ {item.message}</div>
                ))}
                {(activePlanningView?.overload_days || []).map((item, index) => (
                  <div key={`ol-${index}`} style={{ fontSize: '0.8rem', color: 'var(--error)' }}>
                    过载：{item.date} / {item.total_hours}h / 可用 {item.available_hours}h
                  </div>
                ))}
              </div>

              <div style={{ display: 'grid', gap: 8, marginBottom: 'var(--space-sm)' }}>
                {(activePlanningView?.daily_timeline || []).slice(0, 5).map((line, index) => (
                  <div key={index} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{line}</div>
                ))}
              </div>

              <div style={{ display: 'grid', gap: 8, marginBottom: 'var(--space-sm)' }}>
                {Object.entries(activePlanningView?.daily_plan || {}).slice(0, 4).map(([date, info]) => (
                  <div key={date} style={{ padding: '8px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                      <strong style={{ fontSize: '0.82rem' }}>{date}</strong>
                      <span style={{ fontSize: '0.76rem', color: info.overload ? 'var(--error)' : 'var(--text-tertiary)' }}>
                        {info.total_hours}h / {info.available_hours ?? '-'}h
                      </span>
                    </div>
                    {(info.calendar_events || []).length > 0 && (
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>
                        日历占用: {(info.calendar_events || []).map(ev => ev.title).join(' / ')}
                      </div>
                    )}
                    <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      {(info.tasks || []).map(task => `${task.task_name} (${task.hours}h${task.time_slot ? ` / ${task.time_slot}` : ''}${task.energy_type ? ` / ${task.energy_type}` : ''}${task.depends_on?.length ? ` / 依赖:${task.depends_on.join(',')}` : ''})`).join('；')}
                    </div>
                    {(info.time_blocks || []).length > 0 && (
                      <div style={{ marginTop: 6, fontSize: '0.74rem', color: 'var(--text-tertiary)' }}>
                        时间块：{(info.time_blocks || []).map(block => `${block.time_slot} ${block.task_name}${block.energy_type ? `(${block.energy_type})` : ''}`).join('；')}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)', marginBottom: 'var(--space-sm)' }}>
                <div style={{ fontSize: '0.84rem', fontWeight: 600, marginBottom: 8 }}>插入突发任务重排</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 180px auto', gap: 8 }}>
                  <input
                    value={interruptTaskName}
                    onChange={e => setInterruptTaskName(e.target.value)}
                    placeholder="突发任务名称"
                  />
                  <input
                    value={interruptTaskDueTime}
                    onChange={e => setInterruptTaskDueTime(e.target.value)}
                    placeholder="截止时间，如 2026-05-18"
                  />
                  <button className="btn btn-ghost" onClick={replanWithInterrupt} disabled={planningLoading}>
                    重排
                  </button>
                </div>
              </div>

              {replanResult && (
                <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'rgba(10,132,255,0.06)', marginBottom: 'var(--space-sm)' }}>
                  <div style={{ fontSize: '0.84rem', fontWeight: 600, marginBottom: 8 }}>重排影响说明</div>
                  {(replanResult.impact_summary || []).map((item, index) => (
                    <div key={`impact-${index}`} style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 4 }}>{item}</div>
                  ))}
                  {(replanResult.risk_changes || []).map((item, index) => (
                    <div key={`risk-${index}`} style={{ fontSize: '0.78rem', color: 'var(--warning)', marginBottom: 4 }}>⚠️ {item}</div>
                  ))}
                  {(replanResult.conflict_chain || []).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>冲突链</div>
                      {(replanResult.conflict_chain || []).slice(0, 5).map((item, index) => (
                        <div key={`chain-${index}`} style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                          {item.task_name}：{(item.dates || []).join('、') || '无日期'} / {(item.reasons || []).slice(0, 2).join('；')}
                        </div>
                      ))}
                    </div>
                  )}
                  {(replanResult.reordered_tasks || []).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>重排建议</div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                        {[
                          ['all', '全部原因'],
                          ['capacity_conflict', '容量冲突'],
                          ['dependency_conflict', '依赖冲突'],
                          ['calendar_conflict', '日历冲突'],
                          ['time_window_conflict', '时间窗口'],
                          ['optimization', '优化建议'],
                        ].map(([value, label]) => (
                          <button
                            key={value}
                            className={`btn btn-sm ${reasonFilter === value ? 'btn-primary' : 'btn-ghost'}`}
                            onClick={() => setReasonFilter(value)}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                      {mustChangeSuggestions.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--error)', marginBottom: 4 }}>必须调整</div>
                          {mustChangeSuggestions.slice(0, 6).map((item, index) => (
                            <label key={`must-${index}`} style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                              <input
                                type="checkbox"
                                checked={acceptedSuggestions.includes(item.task_name)}
                                onChange={(e) => {
                                  setAcceptedSuggestions(prev =>
                                    e.target.checked
                                      ? [...new Set([...prev, item.task_name])]
                                      : prev.filter(name => name !== item.task_name)
                                  );
                                }}
                                style={{ marginRight: 6 }}
                              />
                              {item.task_name} → {item.suggestion} {item.target_day ? `/ ${item.target_day}` : ''} / {item.reason_type} / 影响 {item.impact_scope?.days || 0}天 {item.impact_scope?.tasks || 0}任务 / 置信度 {Math.round((item.confidence || 0) * 100)}% / {item.reason}
                            </label>
                          ))}
                        </div>
                      )}
                      {optionalSuggestions.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--warning)', marginBottom: 4 }}>可选优化</div>
                          {optionalSuggestions.slice(0, 6).map((item, index) => (
                            <label key={`opt-${index}`} style={{ display: 'block', fontSize: '0.76rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                              <input
                                type="checkbox"
                                checked={acceptedSuggestions.includes(item.task_name)}
                                onChange={(e) => {
                                  setAcceptedSuggestions(prev =>
                                    e.target.checked
                                      ? [...new Set([...prev, item.task_name])]
                                      : prev.filter(name => name !== item.task_name)
                                  );
                                }}
                                style={{ marginRight: 6 }}
                              />
                              {item.task_name} → {item.suggestion} {item.target_day ? `/ ${item.target_day}` : ''} / {item.reason_type} / 影响 {item.impact_scope?.days || 0}天 {item.impact_scope?.tasks || 0}任务 / 置信度 {Math.round((item.confidence || 0) * 100)}% / {item.reason}
                            </label>
                          ))}
                        </div>
                      )}
                      <button className="btn btn-sm btn-ghost" onClick={rerunWithAcceptedSuggestions} disabled={planningLoading}>
                        按已选建议二次重排
                      </button>
                    </div>
                  )}
                  {(replanResult.applied_actions || []).length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>已应用动作</div>
                      {(replanResult.applied_actions || []).slice(0, 6).map((item, index) => (
                        <div key={`applied-${index}`} style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                          {item.task_name} → {item.action} / {item.target_day || '-'} / {item.reason_type || '-'} / {item.severity || '-'} / 影响 {item.impact_scope?.days || 0}天 {item.impact_scope?.tasks || 0}任务 / 置信度 {Math.round(((item.confidence || 0) * 100))}% / {item.reason || '无'}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <button className="btn btn-primary" onClick={confirmPlanning} disabled={planningLoading}>
                {planningLoading ? '创建中...' : '确认创建'}
              </button>
            </div>
          )}

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
              <ChatMessageBubble
                msg={msg}
                isThinking={isThinking && msg.id === messages[messages.length - 1]?.id}
              />
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

      {viewerModal.open && (
        <div className="modal-overlay" onClick={() => setViewerModal({ open: false, type: 'text', title: '', content: '' })}>
          <div className="modal" style={{ width: 'min(92vw, 960px)', maxHeight: '88vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div className="card-header" style={{ marginBottom: 'var(--space-sm)' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>{viewerModal.title}</h3>
              <button className="btn btn-sm btn-ghost" onClick={() => setViewerModal({ open: false, type: 'text', title: '', content: '' })}>
                关闭
              </button>
            </div>
            {viewerModal.type === 'table' ? (
              <div className="markdown-body" dangerouslySetInnerHTML={{ __html: viewerModal.content }} />
            ) : (
              <pre style={{ margin: 0, padding: 12, borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)', border: '1px solid var(--border)', whiteSpace: 'pre-wrap', overflowX: 'auto' }}>
                <code>{viewerModal.content}</code>
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
