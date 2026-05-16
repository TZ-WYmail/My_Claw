import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { apiGet, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import AiChatArchiveTabs from '../components/chat/AiChatArchiveTabs';
import AiChatConfigPanel from '../components/chat/AiChatConfigPanel';
import AiChatManuscriptPage from '../components/chat/AiChatManuscriptPage';
import AiChatMissionBoard from '../components/chat/AiChatMissionBoard';
import AiChatNotesPanel from '../components/chat/AiChatNotesPanel';
import AiChatPlanningPreview from '../components/chat/AiChatPlanningPreview';
import AiChatViewerModal from '../components/chat/AiChatViewerModal';
import {
  PLANNING_TEMPLATE,
  REASON_LABELS,
  parsePlanningDraft,
  createPlanningTask,
  serializePlanningDraft,
  formatPlanningDate,
  buildScheduleLookup,
  sumPlannedHours,
  getRiskTone,
  summarizeText,
  formatMessageStamp,
  buildConversationRounds,
} from '../components/chat/aiChatShared';
import { normalizeList } from '../utils/normalize';

export default function AiChat({ quickAction, clearQuickAction }) {
  const toast = useToast();
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const roundsScrollerRef = useRef(null);
  const mermaidRenderTimerRef = useRef(null);
  const streamingBufferRef = useRef({ assistantId: null, content: '', thinking: '' });
  const streamingFlushTimerRef = useRef(null);

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [currentModel, setCurrentModel] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState('default');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [archiveExpanded, setArchiveExpanded] = useState(false);
  const [currentRoundPage, setCurrentRoundPage] = useState(0);
  const [systemClock, setSystemClock] = useState({
    now: new Date().toISOString(),
    today: '',
    timezone: 'Asia/Shanghai',
    timestamp_ms: Date.now(),
  });

  // Config state
  const [config, setConfig] = useState(null);
  const [configForm, setConfigForm] = useState({ api_base: '', api_key: '', model: '', gateway_base_url: '' });
  const [showConfig, setShowConfig] = useState(false);
  const [testing, setTesting] = useState(false);
  const [planningText, setPlanningText] = useState(PLANNING_TEMPLATE);
  const [planningTasks, setPlanningTasks] = useState(() => parsePlanningDraft(PLANNING_TEMPLATE).map((task, index) => createPlanningTask(task, index)));
  const [planningConstraints, setPlanningConstraints] = useState({
    default_daily_hours: 6,
    weekend_daily_hours: 4,
    buffer_ratio: 0.2,
  });
  const [planningPreview, setPlanningPreview] = useState(null);
  const [planningLoading, setPlanningLoading] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState('balanced');
  const [interruptTaskName, setInterruptTaskName] = useState('');
  const [interruptTaskDueTime, setInterruptTaskDueTime] = useState('');
  const [replanResult, setReplanResult] = useState(null);
  const [acceptedSuggestions, setAcceptedSuggestions] = useState([]);
  const [reasonFilter, setReasonFilter] = useState('all');
  const [viewerModal, setViewerModal] = useState({ open: false, type: 'text', title: '', content: '' });
  const [showRawPlanningEditor, setShowRawPlanningEditor] = useState(false);
  const [draggingTaskId, setDraggingTaskId] = useState(null);
  const deferredPlanningTasks = useDeferredValue(planningTasks);

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
      summary: variantPlan.summary || {},
    };
  }, []);

  const draftedTasks = useMemo(() => (
    deferredPlanningTasks.filter(task => task.task_name?.trim())
  ), [deferredPlanningTasks]);

  const syncPlanningText = useCallback((tasks) => {
    setPlanningText(serializePlanningDraft(tasks));
  }, []);

  const replacePlanningTasks = useCallback((nextTasks) => {
    const normalized = nextTasks.map((task, index) => createPlanningTask(task, index));
    setPlanningTasks(normalized);
    syncPlanningText(normalized);
  }, [syncPlanningText]);

  const updateConstraint = useCallback((field, value) => {
    setPlanningConstraints(prev => ({ ...prev, [field]: value }));
  }, []);

  const updatePlanningTaskField = useCallback((taskId, field, value) => {
    setPlanningTasks(prev => {
      const next = prev.map((task) => {
        if (task.id !== taskId) return task;
        if (field === 'depends_on') {
          return {
            ...task,
            depends_on: value.split(',').map(item => item.trim()).filter(Boolean),
          };
        }
        return { ...task, [field]: value };
      });
      syncPlanningText(next);
      return next;
    });
  }, [syncPlanningText]);

  const addPlanningTask = useCallback(() => {
    setPlanningTasks(prev => {
      const next = [...prev, createPlanningTask({}, prev.length)];
      syncPlanningText(next);
      return next;
    });
  }, [syncPlanningText]);

  const removePlanningTask = useCallback((taskId) => {
    setPlanningTasks(prev => {
      const next = prev.filter(task => task.id !== taskId);
      syncPlanningText(next);
      return next;
    });
  }, [syncPlanningText]);

  const duplicatePlanningTask = useCallback((taskId) => {
    setPlanningTasks(prev => {
      const index = prev.findIndex(task => task.id === taskId);
      if (index < 0) return prev;
      const source = prev[index];
      const duplicated = createPlanningTask({
        ...source,
        key: undefined,
        id: undefined,
        task_name: source.task_name ? `${source.task_name} 副本` : '',
      }, prev.length);
      const next = [...prev.slice(0, index + 1), duplicated, ...prev.slice(index + 1)];
      syncPlanningText(next);
      return next;
    });
  }, [syncPlanningText]);

  const movePlanningTask = useCallback((taskId, direction) => {
    setPlanningTasks(prev => {
      const index = prev.findIndex(task => task.id === taskId);
      const targetIndex = index + direction;
      if (index < 0 || targetIndex < 0 || targetIndex >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      syncPlanningText(next);
      return next;
    });
  }, [syncPlanningText]);

  const reorderPlanningTask = useCallback((fromTaskId, toTaskId) => {
    if (!fromTaskId || !toTaskId || fromTaskId === toTaskId) return;
    setPlanningTasks(prev => {
      const fromIndex = prev.findIndex(task => task.id === fromTaskId);
      const toIndex = prev.findIndex(task => task.id === toTaskId);
      if (fromIndex < 0 || toIndex < 0) return prev;
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      syncPlanningText(next);
      return next;
    });
  }, [syncPlanningText]);

  const applyPlanningTextToCards = useCallback(() => {
    const parsed = parsePlanningDraft(planningText);
    replacePlanningTasks(parsed);
    toast(`已从文本更新 ${parsed.length} 张任务卡`, 'success');
  }, [planningText, replacePlanningTasks, toast]);

  const loadPendingTasksIntoPlanning = useCallback(async () => {
    try {
      const res = await apiPost('/api/task', { action: 'get_pending_tasks', today_only: true });
      if (res.status === 'error') throw new Error(res.message || '载入今日待办失败');
      const pendingTasks = normalizeList(res, ['tasks', 'items']);
      replacePlanningTasks(pendingTasks.map((task) => ({
        task_name: task.task_name,
        due_time: task.due_time ? task.due_time.slice(0, 10) : '',
        earliest_start: task.start_time ? task.start_time.slice(0, 10) : '',
        depends_on: [],
      })));
      toast(`已载入 ${pendingTasks.length} 项今日相关待办`, 'success');
    } catch (e) {
      toast(e.message, 'error');
    }
  }, [replacePlanningTasks, toast]);

  const fetchSystemTime = useCallback(async () => {
    try {
      const res = await apiGet('/api/system/time');
      if (res.status === 'success') {
        setSystemClock({
          now: res.now || new Date().toISOString(),
          today: res.today || '',
          timezone: res.timezone || 'Asia/Shanghai',
          timestamp_ms: res.timestamp_ms || Date.now(),
        });
      }
    } catch {
      // fall back to local ticking state
    }
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
          gateway_base_url: res.config.gateway_base_url || '',
        });
      }
    } catch { /* silent */ }
  }, []);

  // Fetch conversations
  const fetchConversations = useCallback(async () => {
    try {
      const res = await apiGet('/api/chat/conversations');
      if (res.status === 'success') {
        setConversations(normalizeList(res, ['conversations', 'items']));
      }
    } catch { /* silent */ }
  }, []);

  // Load conversation history
  const loadHistory = useCallback(async () => {
    try {
      const res = await apiGet(`/api/chat/history/${activeConvId}`);
      const messages = res.status === 'success' ? normalizeList(res, ['messages', 'items']) : [];
      if (messages.length > 0) {
        setMessages(messages.map((m, i) => ({
          id: m.id || i,
          role: m.role,
          content: m.content || '',
          thinking: m.thinking || '',
          model: m.model || '',
          timestamp: m.timestamp,
        })));
      } else {
        setMessages([]);
      }
    } catch { /* silent */ }
  }, [activeConvId]);

  useEffect(() => { fetchConfig(); fetchConversations(); loadHistory(); fetchSystemTime(); }, [fetchConfig, fetchConversations, loadHistory, fetchSystemTime]);

  useEffect(() => {
    if (quickAction?.type !== 'ai_intent') return;

    if (quickAction.intent === 'plan_today') {
      loadPendingTasksIntoPlanning();
    }

    if (quickAction.intent === 'decompose_task') {
      const taskName = quickAction.task?.task_name || '当前任务';
      setInput(`请把「${taskName}」拆解成 3-6 个可以今天推进的子任务，并给出每项预计时长。`);
    }

    if (quickAction.intent === 'summarize_notes') {
      const taskName = quickAction.task?.task_name || '今天的任务和笔记';
      setInput(`请帮我整理与「${taskName}」相关的工作记录，输出：已完成、阻塞点、下一步。`);
    }

    if (quickAction.intent === 'mail_consult') {
      setInput(quickAction.draftInput || '请帮我分析这封邮件，并给出回复与安排建议。');
    }

    clearQuickAction?.();
  }, [quickAction, clearQuickAction, loadPendingTasksIntoPlanning]);

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
      const messages = res.status === 'success' ? normalizeList(res, ['messages', 'items']) : [];
      if (messages.length > 0) {
        setMessages(messages.map((m, i) => ({
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
    const scroller = roundsScrollerRef.current;
    const anchor = messagesEndRef.current;
    if (!scroller || !anchor) return;
    const nearBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 160;
    if (!nearBottom) return;
    anchor.scrollIntoView({ behavior: streaming ? 'auto' : 'smooth', block: 'end' });
  }, [messages, streaming]);

  useEffect(() => {
    const timer = setInterval(() => {
      setSystemClock((prev) => {
        const nextMs = (prev.timestamp_ms || Date.now()) + 1000;
        const nextIso = new Date(nextMs).toISOString();
        return {
          ...prev,
          now: nextIso,
          timestamp_ms: nextMs,
          today: nextIso.slice(0, 10),
        };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const flushStreamingBuffer = useCallback(() => {
    const { assistantId, content, thinking } = streamingBufferRef.current;
    if (!assistantId || (!content && !thinking)) return;
    setMessages(prev => prev.map(m => (
      m.id === assistantId
        ? {
            ...m,
            content: content ? m.content + content : m.content,
            thinking: thinking ? m.thinking + thinking : m.thinking,
          }
        : m
    )));
    streamingBufferRef.current = { assistantId, content: '', thinking: '' };
  }, []);

  const queueStreamingChunk = useCallback((assistantId, type, chunk) => {
    if (!chunk) return;
    if (streamingBufferRef.current.assistantId !== assistantId) {
      streamingBufferRef.current = { assistantId, content: '', thinking: '' };
    }
    streamingBufferRef.current[type] += chunk;
    if (streamingFlushTimerRef.current) return;
    streamingFlushTimerRef.current = setTimeout(() => {
      flushStreamingBuffer();
      streamingFlushTimerRef.current = null;
    }, 140);
  }, [flushStreamingBuffer]);

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
      const blocks = [...document.querySelectorAll('.markdown-mermaid-source')]
        .filter(block => block.getAttribute('data-mermaid-complete') === 'true');
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

    const hasRenderableMermaid = document.querySelector('.markdown-mermaid-source[data-mermaid-complete="true"]');
    if (!hasRenderableMermaid) {
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
              queueStreamingChunk(assistantId, 'thinking', data.content || '');
              break;

            case 'content':
              setIsThinking(false);
              queueStreamingChunk(assistantId, 'content', data.content || '');
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
              flushStreamingBuffer();
              break;

            case 'error':
              setIsThinking(false);
              flushStreamingBuffer();
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
      flushStreamingBuffer();
      setMessages(prev => prev.map(m =>
        m.id === assistantId ? { ...m, content: `[错误] ${e.message}` } : m
      ));
      toast(e.message, 'error');
    } finally {
      flushStreamingBuffer();
      if (streamingFlushTimerRef.current) {
        clearTimeout(streamingFlushTimerRef.current);
        streamingFlushTimerRef.current = null;
      }
      setStreaming(false);
    }
  }, [input, streaming, activeConvId, toast, flushStreamingBuffer, queueStreamingChunk]);

  // Save config
  const saveConfig = async () => {
    try {
      const res = await apiPost('/api/chat/config', {
        api_base: configForm.api_base.trim(),
        api_key: configForm.api_key.trim(),
        model: configForm.model.trim(),
        gateway_base_url: (configForm.gateway_base_url || '').trim(),
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
    if (draftedTasks.length === 0) {
      toast('请输入任务列表', 'error');
      return;
    }
    setPlanningLoading(true);
    try {
      const tasks = draftedTasks.map(({ task_name, due_time, earliest_start, depends_on }) => ({
        task_name,
        due_time,
        earliest_start,
        depends_on,
      }));
      const res = await apiPost('/api/ai/plan/preview', {
        tasks,
        constraints: {
          default_daily_hours: Number(planningConstraints.default_daily_hours),
          weekend_daily_hours: Number(planningConstraints.weekend_daily_hours),
          buffer_ratio: Number(planningConstraints.buffer_ratio),
        },
      });
      if (res.status === 'error') throw new Error(res.message || '预览失败');
      startTransition(() => {
        setPlanningPreview(res);
        setSelectedVariant(res.variants?.[0]?.id || 'balanced');
        setInterruptTaskName('');
        setInterruptTaskDueTime('');
        setReplanResult(null);
      });
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
    if (draftedTasks.length === 0) {
      toast('请先输入基础任务列表', 'error');
      return;
    }
    if (!interruptTaskName.trim() || !interruptTaskDueTime.trim()) {
      toast('请填写突发任务名称和截止时间', 'error');
      return;
    }
    setPlanningLoading(true);
    try {
      const tasks = draftedTasks.map(({ task_name, due_time, earliest_start, depends_on }) => ({
        task_name,
        due_time,
        earliest_start,
        depends_on,
      }));
      const res = await apiPost('/api/ai/plan/replan', {
        tasks,
        constraints: {
          default_daily_hours: Number(planningConstraints.default_daily_hours),
          weekend_daily_hours: Number(planningConstraints.weekend_daily_hours),
          buffer_ratio: Number(planningConstraints.buffer_ratio),
        },
        interrupt_task: {
          task_name: interruptTaskName.trim(),
          due_time: interruptTaskDueTime.trim(),
        },
      });
      if (res.status === 'error') throw new Error(res.message || '重排失败');
      const suggested = res.suggested_plan || res.new_plan;
      startTransition(() => {
        setPlanningPreview(suggested);
        setSelectedVariant(suggested?.selected_variant || suggested?.variants?.[0]?.id || 'balanced');
        setReplanResult(res);
        setAcceptedSuggestions((res.reordered_tasks || []).map(item => item.task_name));
      });
      toast(`已重排，建议后移 ${res.postpone_candidates?.length || 0} 项任务`, 'success');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setPlanningLoading(false);
    }
  };

  const rerunWithAcceptedSuggestions = async () => {
    if (draftedTasks.length === 0 || !replanResult) return;
    setPlanningLoading(true);
    try {
      const tasks = draftedTasks.map(({ task_name, due_time, earliest_start, depends_on }) => ({
        task_name,
        due_time,
        earliest_start,
        depends_on,
      }));
      const res = await apiPost('/api/ai/plan/replan/accept', {
        tasks,
        constraints: {
          default_daily_hours: Number(planningConstraints.default_daily_hours),
          weekend_daily_hours: Number(planningConstraints.weekend_daily_hours),
          buffer_ratio: Number(planningConstraints.buffer_ratio),
        },
        interrupt_task: interruptTaskName.trim() ? {
          task_name: interruptTaskName.trim(),
          due_time: interruptTaskDueTime.trim(),
        } : null,
        accepted_task_names: acceptedSuggestions,
      });
      if (res.status === 'error') throw new Error(res.message || '二次重排失败');
      startTransition(() => {
        setReplanResult(res);
        setPlanningPreview(res.suggested_plan || res.new_plan);
        setSelectedVariant(res.suggested_plan?.selected_variant || res.new_plan?.selected_variant || 'balanced');
      });
      toast('已按选择建议生成新方案', 'success');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setPlanningLoading(false);
    }
  };

  const activePlanningView = getActivePlanningView(planningPreview, selectedVariant);
  const scheduleLookup = useMemo(() => buildScheduleLookup(activePlanningView), [activePlanningView]);
  const visibleTasks = useMemo(() => (
    (planningPreview?.normalized_tasks?.length ? planningPreview.normalized_tasks : draftedTasks).map((task) => ({
      ...task,
      planned_slots: scheduleLookup[task.task_name] || [],
    }))
  ), [draftedTasks, planningPreview?.normalized_tasks, scheduleLookup]);
  const activeVariant = useMemo(() => (
    (planningPreview?.variants || []).find(variant => variant.id === selectedVariant) || planningPreview?.variants?.[0] || null
  ), [planningPreview?.variants, selectedVariant]);
  const activeSummary = activePlanningView?.summary || activeVariant?.summary || {};
  const planHourTotal = useMemo(() => sumPlannedHours(activePlanningView), [activePlanningView]);
  const reasonOptions = useMemo(() => Object.entries(REASON_LABELS), []);
  const conversationRounds = useMemo(() => buildConversationRounds(messages), [messages]);
  const latestAssistantMessage = useMemo(() => (
    [...messages].reverse().find(message => message.role === 'assistant') || null
  ), [messages]);
  const latestUserMessage = useMemo(() => (
    [...messages].reverse().find(message => message.role === 'user') || null
  ), [messages]);
  const activeRound = conversationRounds[currentRoundPage] || conversationRounds[conversationRounds.length - 1] || null;
  const activeRoundAssistantMessage = activeRound?.assistant || latestAssistantMessage || null;
  const activeRoundUserMessage = activeRound?.user || latestUserMessage || null;
  const latestSignals = useMemo(() => {
    const items = [];
    if (activeRoundAssistantMessage?.tool_calls?.length) {
      items.push({
        type: '执行动作',
        value: `${activeRoundAssistantMessage.tool_calls.length} 个工具调用`,
        tone: 'neutral',
      });
    }
    if (activeRoundAssistantMessage?.thinking?.trim()) {
      items.push({
        type: '推演过程',
        value: `${Math.min(999, activeRoundAssistantMessage.thinking.trim().length)} 字符`,
        tone: 'warn',
      });
    }
    if (planningPreview) {
      items.push({
        type: '计划预览',
        value: `${visibleTasks.length} 项任务 / ${Object.keys(activePlanningView?.daily_plan || {}).length} 天`,
        tone: 'good',
      });
    }
    if (replanResult?.reordered_tasks?.length) {
      items.push({
        type: '重排建议',
        value: `${replanResult.reordered_tasks.length} 条`,
        tone: 'warn',
      });
    }
    if (currentModel) {
      items.push({
        type: '当前模型',
        value: currentModel,
        tone: 'neutral',
      });
    }
    return items.slice(0, 5);
  }, [activeRoundAssistantMessage, planningPreview, visibleTasks.length, activePlanningView, replanResult, currentModel]);

  const messageBoardCards = useMemo(() => {
    const cards = [];

    if (activeRoundAssistantMessage?.content?.trim()) {
      cards.push({
        key: 'conclusion',
        title: '当前结论',
        badge: 'Conclusion',
        tone: 'neutral',
        content: summarizeText(activeRoundAssistantMessage.content, 180),
      });
    }

    if (activeRoundAssistantMessage?.thinking?.trim()) {
      cards.push({
        key: 'thinking',
        title: '推演线索',
        badge: 'Thinking',
        tone: 'warn',
        content: summarizeText(activeRoundAssistantMessage.thinking, 180),
      });
    }

    if (planningPreview) {
      cards.push({
        key: 'plan',
        title: '预览战报',
        badge: getRiskTone(activeSummary.risk_level).label,
        tone: activeSummary.risk_level === 'high' ? 'danger' : activeSummary.risk_level === 'medium' ? 'warn' : 'good',
        content: activePlanningView?.explanation?.summary || planningPreview.explanation?.summary || `已生成 ${visibleTasks.length} 项任务的排程预览`,
      });
    }

    if ((activePlanningView?.conflicts || []).length || (activePlanningView?.overload_days || []).length || (activePlanningView?.infeasible_tasks || []).length) {
      const riskCount = (activePlanningView?.conflicts || []).length + (activePlanningView?.overload_days || []).length + (activePlanningView?.infeasible_tasks || []).length;
      cards.push({
        key: 'risk',
        title: '风险雷达',
        badge: `${riskCount} 项`,
        tone: 'danger',
        content: (activePlanningView?.conflicts?.[0]?.message)
          || (activePlanningView?.infeasible_tasks?.[0] ? `${activePlanningView.infeasible_tasks[0].task_name}：${activePlanningView.infeasible_tasks[0].reason}` : '')
          || (activePlanningView?.overload_days?.[0] ? `${activePlanningView.overload_days[0].date} 过载 ${activePlanningView.overload_days[0].total_hours}h` : ''),
      });
    }

    if (replanResult?.reordered_tasks?.length) {
      cards.push({
        key: 'replan',
        title: '重排动作',
        badge: `${acceptedSuggestions.length} 已选`,
        tone: 'warn',
        content: replanResult.impact_summary?.[0]
          || replanResult.risk_changes?.[0]
          || replanResult.reordered_tasks?.[0]?.reason
          || '已有可应用的重排建议',
      });
    }

    if (activeRoundUserMessage?.content?.trim()) {
      cards.push({
        key: 'intent',
        title: '最近指令',
        badge: 'Intent',
        tone: 'neutral',
        content: summarizeText(activeRoundUserMessage.content, 120),
      });
    }

    return cards.slice(0, 6);
  }, [
    activeRoundAssistantMessage,
    planningPreview,
    activeSummary.risk_level,
    activePlanningView,
    visibleTasks.length,
    replanResult,
    acceptedSuggestions.length,
    activeRoundUserMessage,
  ]);
  const activeConversationMeta = useMemo(() => (
    conversations.find(conv => conv.id === activeConvId) || null
  ), [conversations, activeConvId]);
  const currentDisplayTime = useMemo(() => formatMessageStamp(systemClock.now), [systemClock.now]);

  useEffect(() => {
    if (!conversationRounds.length) {
      setCurrentRoundPage(0);
      return;
    }
    setCurrentRoundPage(conversationRounds.length - 1);
  }, [activeConvId, conversationRounds.length]);

  // Handle Enter
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="page-shell atlas-page-shell ai-command-shell">
      <div className="ai-command-main">
        <section className="atlas-chapter-head">
          <div>
            <div className="section-kicker">ADVISER MANUSCRIPT</div>
            <h1 className="atlas-chapter-title">参谋手稿台</h1>
            <div className="atlas-chapter-copy">
              保留对话、规划、预览与重排的原工作流，只把它纳入行动地图册的章节体系。左页看回合脉络，右页看计划落点，中缝持续维持今天的执行上下文。
            </div>
          </div>
          <aside className="atlas-chapter-note ai-command-note">
            <div className="atlas-chapter-note-title">Chapter Role</div>
            <div className="atlas-chapter-note-copy">
              这是整本地图册里的参谋插页。它负责把目标、风险、任务顺序和临时打断收拢成一份可执行手稿，而不是另一条冗长聊天流。
            </div>
          </aside>
        </section>

        <div className="card war-room-hero ai-command-hero">
          <div className="mission-masthead-grid">
            <div>
              <div className="section-kicker">Adviser Room</div>
              <h2 className="mission-title">AI 参谋室</h2>
              <div className="mission-copy">
                对话不再只是消息竖排。每一次提问都变成一个回合，左侧看指令脉络，右侧看结果战报，中间持续推进今天的作战计划。
              </div>
              <div className="mission-chip-row">
                <span className="war-room-stamp">{activeConversationMeta?.title || '当前对话'}</span>
                <span className="war-room-stamp">{conversationRounds.length} 个回合</span>
                {currentModel && <span className="war-room-stamp">{currentModel}</span>}
                {planningPreview && <span className="war-room-stamp">已有预览方案</span>}
                {isThinking && <span className="war-room-stamp danger">AI 推演中</span>}
              </div>
            </div>
            <div className="mission-sidecard ai-hero-sidecard">
              <div className="mission-sidecard-title">CURRENT SIGNAL</div>
              <div className="mission-sidecard-copy">
                {messageBoardCards[0]?.content || '先给 AI 一个明确目标，它会把回复、计划、风险和重排结果聚成一块，而不是散在长聊天流里。'}
              </div>
              <div className="ai-signal-strip">
                {latestSignals.map((item) => (
                  <div key={`${item.type}-${item.value}`} className={`ai-signal-chip ${item.tone}`}>
                    <span>{item.type}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="ai-book-spread-shell">
          {sidebarOpen && (
            <AiChatArchiveTabs
              conversations={conversations}
              activeConvId={activeConvId}
              createConversation={createConversation}
              switchConversation={switchConversation}
              deleteConversation={deleteConversation}
              expanded={archiveExpanded}
              setExpanded={setArchiveExpanded}
            />
          )}

          <div className="ai-book-spread">
            <section className="ai-book-page left">
              <AiChatManuscriptPage
                conversationRounds={conversationRounds}
                activeRound={activeRound}
                currentRoundPage={currentRoundPage}
                setCurrentRoundPage={setCurrentRoundPage}
                latestAssistantMessage={latestAssistantMessage}
                latestUserMessage={latestUserMessage}
                formatMessageStamp={formatMessageStamp}
                inputRef={inputRef}
                input={input}
                setInput={setInput}
                handleKeyDown={handleKeyDown}
                streaming={streaming}
                sendMessage={sendMessage}
                loadPendingTasksIntoPlanning={loadPendingTasksIntoPlanning}
                messagesEndRef={messagesEndRef}
                roundsScrollerRef={roundsScrollerRef}
                sidebarOpen={sidebarOpen}
                setSidebarOpen={setSidebarOpen}
                showConfig={showConfig}
                setShowConfig={setShowConfig}
                currentDisplayTime={currentDisplayTime}
              />
            </section>

            <section className="ai-book-page right">
              <div className="card ai-results-panel ai-book-chapter ai-report-chapter">
                <div className="board-lane-header ai-book-page-header ai-report-header">
                  <div>
                    <div className="section-kicker">Result Bay</div>
                    <div className="board-lane-title">当前战报舱</div>
                    <div className="board-lane-copy">
                      把回复、计划、风险和执行动作拆成可扫读的情报卡。
                    </div>
                  </div>
                  {activeRound && (
                    <span className="war-room-stamp">锁定 Round {String(activeRound.index).padStart(2, '0')}</span>
                  )}
                </div>

                <div className="ai-message-board ai-report-ledger">
                  {messageBoardCards.length === 0 && (
                    <div className="ai-board-empty">结果战报会在首次对话或生成计划后出现。</div>
                  )}
                  {messageBoardCards.map((card) => (
                    <div key={card.key} className={`ai-message-card ${card.tone}`}>
                      <div className="ai-message-card-head">
                        <span>{card.title}</span>
                        <strong>{card.badge}</strong>
                      </div>
                      <div className="ai-message-card-copy">{card.content}</div>
                    </div>
                  ))}
                </div>
              </div>

              <AiChatNotesPanel
                activeRoundAssistantMessage={activeRoundAssistantMessage}
                activeRound={activeRound}
                planningPreview={planningPreview}
                activePlanningView={activePlanningView}
                visibleTasks={visibleTasks}
                activeSummary={activeSummary}
                planHourTotal={planHourTotal}
                formatPlanningDate={formatPlanningDate}
              />

              <AiChatMissionBoard
                planningTasks={planningTasks}
                visibleTasks={visibleTasks}
                draggingTaskId={draggingTaskId}
                setDraggingTaskId={setDraggingTaskId}
                reorderPlanningTask={reorderPlanningTask}
                movePlanningTask={movePlanningTask}
                duplicatePlanningTask={duplicatePlanningTask}
                removePlanningTask={removePlanningTask}
                updatePlanningTaskField={updatePlanningTaskField}
                formatPlanningDate={formatPlanningDate}
                addPlanningTask={addPlanningTask}
                showRawPlanningEditor={showRawPlanningEditor}
                setShowRawPlanningEditor={setShowRawPlanningEditor}
                draftedTasksCount={draftedTasks.length}
                planningText={planningText}
                setPlanningText={setPlanningText}
                planningTemplate={PLANNING_TEMPLATE}
                applyPlanningTextToCards={applyPlanningTextToCards}
                planningConstraints={planningConstraints}
                updateConstraint={updateConstraint}
                previewPlanning={previewPlanning}
                planningLoading={planningLoading}
                loadPendingTasksIntoPlanning={loadPendingTasksIntoPlanning}
                fillPlanningTemplate={() => replacePlanningTasks(parsePlanningDraft(PLANNING_TEMPLATE))}
                clearPlanningPreview={() => setPlanningPreview(null)}
                hasPlanningPreview={Boolean(planningPreview)}
              />

              <AiChatPlanningPreview
                planningPreview={planningPreview}
                activePlanningView={activePlanningView}
                selectedVariant={selectedVariant}
                setSelectedVariant={setSelectedVariant}
                getRiskTone={getRiskTone}
                activeSummary={activeSummary}
                planHourTotal={planHourTotal}
                visibleTasks={visibleTasks}
                formatPlanningDate={formatPlanningDate}
                interruptTaskName={interruptTaskName}
                setInterruptTaskName={setInterruptTaskName}
                interruptTaskDueTime={interruptTaskDueTime}
                setInterruptTaskDueTime={setInterruptTaskDueTime}
                replanWithInterrupt={replanWithInterrupt}
                planningLoading={planningLoading}
                replanResult={replanResult}
                reasonOptions={reasonOptions}
                reasonFilter={reasonFilter}
                setReasonFilter={setReasonFilter}
                mustChangeSuggestions={mustChangeSuggestions}
                optionalSuggestions={optionalSuggestions}
                acceptedSuggestions={acceptedSuggestions}
                setAcceptedSuggestions={setAcceptedSuggestions}
                rerunWithAcceptedSuggestions={rerunWithAcceptedSuggestions}
                confirmPlanning={confirmPlanning}
              />

            <AiChatConfigPanel
              showConfig={showConfig}
              setShowConfig={setShowConfig}
              configForm={configForm}
              setConfigForm={setConfigForm}
              saveConfig={saveConfig}
              testConnection={testConnection}
              testing={testing}
              clearChat={clearChat}
              config={config}
            />
          </section>
          </div>
        </div>

      </div>

      <AiChatViewerModal
        viewerModal={viewerModal}
        setViewerModal={setViewerModal}
      />
    </div>
  );
}
