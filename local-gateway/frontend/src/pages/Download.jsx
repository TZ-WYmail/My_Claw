import { useState, useEffect, useCallback, useMemo } from 'react';
import { useApi, apiGet, apiPost, apiPut } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';
import { normalizeList } from '../utils/normalize';

const FOLDER_OPTIONS = [
  { value: '', label: '全部信箱' },
  { value: 'inbox', label: '收件箱' },
  { value: 'archive', label: '归档' },
  { value: 'sent', label: '已发出' },
  { value: 'drafts', label: '草稿' },
];

const TONE_OPTIONS = [
  { value: 'plain', label: '克制' },
  { value: 'warm', label: '温和' },
  { value: 'romantic', label: '书信式' },
];

const AUTO_MAIL_POLICY_OPTIONS = [
  { value: 'draft_only', label: '只起草，不触发确认' },
  { value: 'draft_and_notify', label: '起草后等我确认' },
  { value: 'auto_send', label: '自动寄出回信' },
];

function getInboxLabel(folder) {
  if (folder === 'archive') return '已归档';
  if (folder === 'sent') return '已发出';
  if (folder === 'drafts') return '草稿';
  return '收件箱';
}

function formatDateTime(value) {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function getReplyLevelLabel(level) {
  if (level === 'must_reply') return '必须回信';
  if (level === 'suggest_reply') return '建议回复';
  return '仅供阅读';
}

function getMailKindLabel(kind) {
  if (kind === 'planning') return '规划相关';
  if (kind === 'reply') return '往返信件';
  if (kind === 'marketing') return '营销订阅';
  if (kind === 'outbound') return '已发信';
  return '信息信件';
}

function getRiskBadgeClass(level) {
  if (level === 'high') return 'badge-error';
  if (level === 'low') return 'badge-completed';
  return 'badge-warning';
}

function getAutoMailPolicyLabel(policy) {
  if (policy === 'draft_only') return '只起草';
  if (policy === 'auto_send') return '自动寄出';
  return '起草待确认';
}

function getAgentRunStatusLabel(status) {
  if (status === 'draft_created') return '已起草';
  if (status === 'user_confirmation_required') return '待你确认';
  if (status === 'sent') return '已自动寄出';
  if (status === 'failed') return '执行失败';
  if (status === 'skipped_non_direct') return '跳过非直接来信';
  if (status === 'skipped') return '已跳过';
  return status || '未记录';
}

function getAgentRunStatusBadge(status) {
  if (status === 'sent') return 'badge-completed';
  if (status === 'failed') return 'badge-error';
  if (status === 'skipped_non_direct' || status === 'skipped') return 'badge-ghost';
  return 'badge-warning';
}

function getAgentRunReasonLabel(reasonCode) {
  if (reasonCode === 'non_direct_thread') return '判定为非直接协商来信';
  if (reasonCode === 'draft_generation_failed') return '起草阶段失败';
  if (reasonCode === 'policy_draft_only') return '策略要求只起草';
  if (reasonCode === 'policy_requires_confirmation') return '策略要求等待确认';
  if (reasonCode === 'policy_auto_send') return '策略允许自动寄出';
  if (reasonCode === 'send_failed') return '发信阶段失败';
  return '';
}

function getAutoPolicyNarrative(policy) {
  if (policy === 'draft_only') return '来信到了先落草稿，不打扰你做最终决定。';
  if (policy === 'auto_send') return '来信一旦命中自动处理链路，代理会直接替你把回信寄出去。';
  return '来信先被起草，再回到你的案头，等你拍板。';
}

const MAIL_ALLOWED_TAGS = new Set([
  'a', 'p', 'br', 'div', 'span', 'strong', 'b', 'em', 'i', 'u', 's',
  'blockquote', 'pre', 'code', 'ul', 'ol', 'li', 'hr',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
]);

const MAIL_UNWRAP_ONLY_TAGS = new Set([
  'html', 'body', 'head', 'section', 'article', 'main', 'header', 'footer',
]);

const MAIL_DROP_TAGS = new Set([
  'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button',
  'textarea', 'select', 'option', 'svg', 'math', 'canvas', 'video', 'audio',
  'source', 'picture', 'img', 'link', 'meta', 'base',
]);

function sanitizeMailHref(rawHref) {
  if (!rawHref) return '';
  const href = rawHref.trim();
  if (!href) return '';
  if (
    href.startsWith('/') ||
    href.startsWith('./') ||
    href.startsWith('../') ||
    href.startsWith('#') ||
    href.startsWith('?')
  ) {
    return href;
  }
  try {
    const parsed = new URL(href, window.location.origin);
    if (['http:', 'https:', 'mailto:', 'tel:'].includes(parsed.protocol.toLowerCase())) {
      return parsed.href;
    }
  } catch {
    return '';
  }
  return '';
}

function sanitizeMailHtml(rawHtml) {
  if (!rawHtml || typeof window === 'undefined') return '';
  const parser = new window.DOMParser();
  const doc = parser.parseFromString(rawHtml, 'text/html');

  const unwrapElement = (node) => {
    const parent = node.parentNode;
    if (!parent) return;
    while (node.firstChild) {
      parent.insertBefore(node.firstChild, node);
    }
    parent.removeChild(node);
  };

  Array.from(doc.body.querySelectorAll('*')).forEach((node) => {
    const tag = node.tagName.toLowerCase();
    if (MAIL_DROP_TAGS.has(tag)) {
      node.remove();
      return;
    }
    if (MAIL_UNWRAP_ONLY_TAGS.has(tag)) {
      unwrapElement(node);
      return;
    }
    if (!MAIL_ALLOWED_TAGS.has(tag)) {
      unwrapElement(node);
      return;
    }

    Array.from(node.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase();
      if (name.startsWith('on') || name === 'style' || name === 'class' || name === 'id') {
        node.removeAttribute(attr.name);
        return;
      }
      if (tag === 'a' && name === 'href') {
        const safeHref = sanitizeMailHref(attr.value);
        if (safeHref) {
          node.setAttribute('href', safeHref);
        } else {
          node.removeAttribute(attr.name);
        }
        return;
      }
      if (!['href', 'title', 'colspan', 'rowspan'].includes(name)) {
        node.removeAttribute(attr.name);
      }
    });

    if (tag === 'a') {
      if (!node.getAttribute('href')) {
        unwrapElement(node);
        return;
      }
      node.setAttribute('target', '_blank');
      node.setAttribute('rel', 'noopener noreferrer nofollow');
    }
  });

  return doc.body.innerHTML.trim();
}

function normalizePlainLink(rawValue) {
  const match = rawValue.match(/^(.*?)([),.;!?]+)?$/);
  const core = (match?.[1] || rawValue).trim();
  const suffix = match?.[2] || '';
  if (!core) return null;

  if (/^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(core)) {
    return { href: `mailto:${core}`, label: core, suffix };
  }

  if (/^www\./i.test(core)) {
    return { href: `https://${core}`, label: core, suffix };
  }

  const href = sanitizeMailHref(core);
  if (!href) return null;
  return { href, label: core, suffix };
}

function renderPlainTextWithLinks(text) {
  const source = text || '这封信还没有正文。';
  const lines = source.split(/\r?\n/);
  const pattern = /((?:https?:\/\/|mailto:|tel:)[^\s<]+|www\.[^\s<]+|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})/gi;

  return lines.map((line, lineIndex) => {
    const nodes = [];
    let cursor = 0;
    let match;
    pattern.lastIndex = 0;
    while ((match = pattern.exec(line)) !== null) {
      const [token] = match;
      const start = match.index;
      if (start > cursor) {
        nodes.push(line.slice(cursor, start));
      }
      const normalized = normalizePlainLink(token);
      if (normalized) {
        nodes.push(
          <a key={`${lineIndex}-${start}`} href={normalized.href} target="_blank" rel="noopener noreferrer nofollow">
            {normalized.label}
          </a>,
        );
        if (normalized.suffix) {
          nodes.push(normalized.suffix);
        }
      } else {
        nodes.push(token);
      }
      cursor = start + token.length;
    }
    if (cursor < line.length) {
      nodes.push(line.slice(cursor));
    }
    return (
      <span key={`line-${lineIndex}`}>
        {nodes}
        {lineIndex < lines.length - 1 && <br />}
      </span>
    );
  });
}

function DecisionQueueCard({ thread, onOpen, onDiscuss, onCreateTask }) {
  return (
    <article className="dossier-card" style={{ transform: 'rotate(-0.35deg)', borderColor: 'var(--warning)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
        <div>
          <div className="section-kicker">PENDING DECISION</div>
          <h3 className="dossier-title" style={{ marginBottom: 6 }}>{thread.subject}</h3>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{thread.analysis_reason || '这封信仍在等待你的判断。'}</div>
        </div>
        <span className={`badge ${getRiskBadgeClass(thread.risk_level)}`}>{getReplyLevelLabel(thread.reply_level)}</span>
      </div>
      <div className="mission-chip-row" style={{ marginTop: 'var(--space-md)' }}>
        <span className="badge badge-ghost">{getMailKindLabel(thread.mail_kind)}</span>
        {(thread.action_suggestions || []).slice(0, 3).map((item) => (
          <span key={item} className="badge badge-pending">{item}</span>
        ))}
      </div>
      <div className="inline-actions" style={{ marginTop: 'var(--space-md)' }}>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => onOpen(thread.thread_id)}>翻开这封信</button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => onCreateTask(thread)}>转成任务</button>
        <button type="button" className="btn btn-sm btn-primary" onClick={() => onDiscuss(thread)}>和 AI 商量</button>
      </div>
    </article>
  );
}

function ThreadCard({ thread, active, onOpen }) {
  const participants = thread.participants || [];
  const lead = participants[0]?.name || participants[0]?.email || '未命名来信';
  return (
    <button
      type="button"
      className="dossier-card"
      onClick={() => onOpen(thread.thread_id)}
      style={{
        textAlign: 'left',
        width: '100%',
        transform: active ? 'rotate(-0.3deg) translateY(-2px)' : 'rotate(0.6deg)',
        borderColor: active ? 'var(--accent)' : undefined,
        boxShadow: active ? 'var(--shadow-md)' : undefined,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
        <div style={{ minWidth: 0 }}>
          <div className="section-kicker">{thread.needs_reply ? '待回信' : '信件线程'}</div>
          <h3 className="dossier-title" style={{ marginBottom: 6 }}>{thread.subject}</h3>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>{lead}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          {!!thread.unread_count && <span className="badge badge-error">{thread.unread_count} 未读</span>}
          {thread.has_draft && <span className="badge badge-pending">有草稿</span>}
          {thread.waiting_user_decision && <span className={`badge ${getRiskBadgeClass(thread.risk_level)}`}>{getReplyLevelLabel(thread.reply_level)}</span>}
        </div>
      </div>

      <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '10px 0 14px' }}>
        {thread.snippet || '这封信还没有留下摘要。'}
      </div>

      {thread.analysis_reason && (
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: 12 }}>
          {thread.analysis_reason}
        </div>
      )}

      <div className="dossier-meta-grid">
        <div className="dossier-meta-box">
          <div className="dossier-meta-label">信箱</div>
          <div>{getInboxLabel(thread.latest_folder_kind)}</div>
        </div>
        <div className="dossier-meta-box">
          <div className="dossier-meta-label">最近来往</div>
          <div>{formatDateTime(thread.latest_message_at)}</div>
        </div>
        <div className="dossier-meta-box">
          <div className="dossier-meta-label">参谋判断</div>
          <div>{getMailKindLabel(thread.mail_kind)}</div>
        </div>
      </div>

      <div style={{ marginTop: 'var(--space-md)', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
        点开这封信后，再决定是回信、转任务，还是交给邮件处理页继续。
      </div>
    </button>
  );
}

function ArchiveThreadRow({ thread, active, onOpen }) {
  const participants = thread.participants || [];
  const lead = participants[0]?.name || participants[0]?.email || '未命名来信';
  return (
    <button
      type="button"
      className="signal-row"
      onClick={() => onOpen(thread.thread_id)}
      style={{
        width: '100%',
        textAlign: 'left',
        border: active ? '1px solid var(--accent)' : undefined,
        background: active ? 'rgba(158, 132, 94, 0.08)' : undefined,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="signal-row-title" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <span>{thread.subject}</span>
          <span className="badge badge-ghost">已归档</span>
        </div>
        <div className="signal-row-copy">
          {formatDateTime(thread.latest_message_at)} · {lead}
        </div>
      </div>
    </button>
  );
}

function MessagePaper({ message }) {
  const sanitizedHtml = useMemo(() => sanitizeMailHtml(message.html_body), [message.html_body]);
  const plainBody = message.text_body || (!sanitizedHtml ? message.html_body : '') || '';
  const attachments = message.attachments || [];

  return (
    <article className="dossier-card mail-message-paper" style={{ transform: `rotate(${message.direction === 'inbound' ? '-0.5deg' : '0.4deg'})` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
        <div>
          <div className="section-kicker">{message.direction === 'inbound' ? '来信' : '寄出'}</div>
          <h3 className="dossier-title" style={{ marginBottom: 6 }}>
            {message.from_name || message.from_email || '未命名发件人'}
          </h3>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            {message.from_email || '无邮箱地址'}
          </div>
        </div>
        <span className={`badge ${message.direction === 'inbound' ? 'badge-warning' : 'badge-completed'}`}>
          {message.direction === 'inbound' ? '收到' : '已寄出'}
        </span>
      </div>
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '8px 0 12px' }}>
        {formatDateTime(message.received_at || message.sent_at || message.created_at)}
      </div>
      <div className="mail-message-body">
        {sanitizedHtml ? (
          <div className="mail-rich-body" dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />
        ) : (
          <div className="mail-plain-body">
            {renderPlainTextWithLinks(plainBody)}
          </div>
        )}
      </div>
      {attachments.length > 0 && (
        <div className="signal-list" style={{ marginTop: 'var(--space-md)' }}>
          {attachments.map((attachment) => (
            <div key={attachment.attachment_id} className="signal-row">
              <div>
                <div className="signal-row-title">{attachment.filename || '未命名附件'}</div>
                <div className="signal-row-copy">
                  {attachment.mime_type} · {attachment.size_bytes || 0} B{attachment.is_inline ? ' · 内嵌资源' : ''}
                </div>
              </div>
              <span className="badge badge-ghost">附件</span>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

export default function Download({ quickAction = null, clearQuickAction = null, onOpenNotifyNetwork = null, onOpenAi = null }) {
  const toast = useToast();
  const { loading, request } = useApi();

  const [dashboard, setDashboard] = useState(null);
  const [threads, setThreads] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState('');
  const [selectedFolder, setSelectedFolder] = useState('');
  const [selectedThreadId, setSelectedThreadId] = useState('');
  const [threadDetail, setThreadDetail] = useState(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);

  const [draftForm, setDraftForm] = useState({
    account_id: '',
    to: '',
    cc: '',
    bcc: '',
    subject: '',
    body_html: '',
    tone_mode: 'warm',
    signature: '',
  });

  const activeAccount = accounts.find(item => item.account_id === selectedAccount) || accounts[0] || null;

  const openPortalPage = useCallback((thread) => {
    if (!thread?.portal_url) {
      toast('这封信还没有可打开的处理页链接', 'error');
      return;
    }
    window.open(thread.portal_url, '_blank', 'noopener,noreferrer');
  }, [toast]);

  const copyPortalLink = useCallback(async (thread) => {
    if (!thread?.portal_url) {
      toast('这封信还没有可复制的处理页链接', 'error');
      return;
    }
    try {
      await navigator.clipboard.writeText(thread.portal_url);
      toast('处理页链接已复制', 'success');
    } catch {
      toast('复制链接失败', 'error');
    }
  }, [toast]);
  const decisionQueue = useMemo(
    () => threads.filter(item => item.waiting_user_decision && item.latest_folder_kind !== 'archive'),
    [threads],
  );
  const selectedThreadIndex = useMemo(
    () => threads.findIndex(item => item.thread_id === selectedThreadId),
    [threads, selectedThreadId],
  );
  const railThread = threads[selectedThreadIndex >= 0 ? selectedThreadIndex : 0] || null;

  const parseRecipientLine = (value) => {
    return value
      .split(/[,\n]/)
      .map(item => item.trim())
      .filter(Boolean)
      .map(email => ({ email, name: email.split('@')[0] || email }));
  };

  const fetchAccounts = useCallback(async () => {
    const data = await apiGet('/api/mail/accounts');
    const items = normalizeList(data, ['accounts']);
    setAccounts(items);
    setSelectedAccount((current) => current || items[0]?.account_id || '');
    setDraftForm((prev) => ({
      ...prev,
      account_id: prev.account_id || items[0]?.account_id || '',
      signature: prev.signature || items[0]?.signature_text || '',
      tone_mode: prev.tone_mode || items[0]?.tone_mode || 'warm',
    }));
  }, []);

  const fetchDashboard = useCallback(async (accountId = '') => {
    const suffix = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
    const data = await apiGet(`/api/mail/dashboard${suffix}`);
    setDashboard(data.summary || null);
  }, []);

  const fetchThreads = useCallback(async (accountId = '', folder = '') => {
    const params = new URLSearchParams();
    if (accountId) params.set('account_id', accountId);
    if (folder) params.set('folder', folder);
    const query = params.toString();
    const data = await apiGet(`/api/mail/threads${query ? `?${query}` : ''}`);
    const items = normalizeList(data, ['threads']);
    setThreads(items);
    setSelectedThreadId((current) => (
      current && items.some(item => item.thread_id === current)
        ? current
        : (items[0]?.thread_id || '')
    ));
  }, []);

  const fetchSyncStatus = useCallback(async (accountId) => {
    if (!accountId) {
      setSyncStatus(null);
      return;
    }
    try {
      const data = await apiGet(`/api/mail/accounts/${accountId}/sync-status`);
      setSyncStatus(data.latest_run || null);
    } catch {
      setSyncStatus(null);
    }
  }, []);

  const fetchThreadDetail = useCallback(async (threadId) => {
    if (!threadId) {
      setThreadDetail(null);
      return;
    }
    const data = await apiGet(`/api/mail/threads/${threadId}`);
    setThreadDetail(data);
  }, []);

  const refreshAll = useCallback(async (accountId = selectedAccount, folder = selectedFolder) => {
    await Promise.all([
      fetchAccounts(),
      fetchDashboard(accountId),
      fetchThreads(accountId, folder),
      fetchSyncStatus(accountId),
    ]);
  }, [fetchAccounts, fetchDashboard, fetchThreads, fetchSyncStatus, selectedAccount, selectedFolder]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    fetchDashboard(selectedAccount);
    fetchThreads(selectedAccount, selectedFolder);
    fetchSyncStatus(selectedAccount);
  }, [fetchDashboard, fetchThreads, fetchSyncStatus, selectedAccount, selectedFolder]);

  useEffect(() => {
    fetchThreadDetail(selectedThreadId);
  }, [fetchThreadDetail, selectedThreadId]);

  useEffect(() => {
    if (activeAccount) {
      setDraftForm((prev) => ({
        ...prev,
        account_id: prev.account_id || activeAccount.account_id,
        signature: prev.signature || activeAccount.signature_text || '',
      }));
    }
  }, [activeAccount]);

  useEffect(() => {
    if (!quickAction) return;
    if (quickAction.type === 'notify_network_ready') {
      refreshAll();
      clearQuickAction?.();
    }
  }, [quickAction, clearQuickAction, refreshAll]);

  const handleComposeSubmit = async (e) => {
    e.preventDefault();
    if (!draftForm.account_id) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    if (!draftForm.subject.trim()) {
      toast('请填写主题', 'warning');
      return;
    }
    if (!draftForm.to.trim()) {
      toast('请填写至少一个收件人', 'warning');
      return;
    }
    try {
      const draft = await request(() => apiPost('/api/mail/drafts', {
        account_id: draftForm.account_id,
        subject: draftForm.subject.trim(),
        body_html: draftForm.body_html.trim(),
        to: parseRecipientLine(draftForm.to),
        cc: parseRecipientLine(draftForm.cc),
        bcc: parseRecipientLine(draftForm.bcc),
        tone_mode: draftForm.tone_mode,
        signature: draftForm.signature,
      }));
      await request(() => apiPost(`/api/mail/drafts/${draft.draft_id}/send`, {}));
      toast('信已经寄出', 'success');
      setComposerOpen(false);
      setDraftForm((prev) => ({
        ...prev,
        to: '',
        cc: '',
        bcc: '',
        subject: '',
        body_html: '',
      }));
      await refreshAll(draftForm.account_id, selectedFolder);
      setSelectedThreadId(draft.thread_id);
    } catch (e2) {
      toast(e2.message || '寄信失败', 'error');
    }
  };

  const handleArchive = async (threadId) => {
    try {
      await request(() => apiPost(`/api/mail/threads/${threadId}/archive`, {}));
      toast('这封信已收进归档夹', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedFolder !== 'archive' && selectedThreadId === threadId) {
        setSelectedThreadId('');
        setThreadDetail(null);
      } else if (selectedThreadId === threadId) {
        await fetchThreadDetail(threadId);
      }
    } catch (e) {
      toast(e.message || '归档失败', 'error');
    }
  };

  const handleMarkRead = async (threadId) => {
    try {
      await request(() => apiPost(`/api/mail/threads/${threadId}/mark-read`, {}));
      toast('已把这封信翻到已读一侧', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId === threadId) {
        await fetchThreadDetail(threadId);
      }
    } catch (e) {
      toast(e.message || '标记已读失败', 'error');
    }
  };

  const handleSyncInbox = async () => {
    if (!selectedAccount) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    setSyncing(true);
    try {
      const data = await request(() => apiPost(`/api/mail/accounts/${selectedAccount}/sync?folder_kind=inbox&limit=20`, {}));
      toast(`收件箱已同步，新增 ${data.new_count ?? 0} 封信`, 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '同步收件箱失败', 'error');
    } finally {
      setSyncing(false);
    }
  };

  const handleDecisionStatus = async (threadId, decisionStatus) => {
    try {
      await request(() => apiPost(`/api/mail/threads/${threadId}/decision`, { decision_status: decisionStatus }));
      toast(decisionStatus === 'snoozed' ? '这封信稍后再来叩门' : '这封信先从待裁决队列退下', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId === threadId) {
        await fetchThreadDetail(threadId);
      }
    } catch (e) {
      toast(e.message || '更新决策状态失败', 'error');
    }
  };

  const handleDiscussWithAi = (thread) => {
    const latestMessage = thread.thread_id === selectedThreadId
      ? (threadDetail?.messages || []).slice(-1)[0]
      : null;
    const participants = (thread.participants || []).map(item => item.email || item.name).filter(Boolean).join(', ');
    const summary = latestMessage?.text_body || latestMessage?.html_body || thread.snippet || '';
    onOpenAi?.({
      intent: 'mail_consult',
      thread,
      draftInput: `请作为书信参谋，帮我处理这封邮件。\n主题：${thread.subject}\n分类：${getMailKindLabel(thread.mail_kind)}\n回信强度：${getReplyLevelLabel(thread.reply_level)}\n判断理由：${thread.analysis_reason || '暂无'}\n相关参与者：${participants || '未记录'}\n邮件摘要：${summary.slice(0, 1200)}\n\n请输出：\n1. 我是否必须回复\n2. 若回复，给出建议语气与核心要点\n3. 若涉及安排，请给出任务/日程建议`,
    });
  };

  const handleCreateTaskFromMail = async (thread) => {
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${thread.thread_id}/create-task`, {
        task_name: `邮件跟进：${thread.subject}`,
        priority: thread.risk_level === 'high' ? 1 : 2,
      }));
      toast(`已落成任务：${data.task_name}`, 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId === thread.thread_id) {
        await fetchThreadDetail(thread.thread_id);
      }
    } catch (e) {
      toast(e.message || '从邮件创建任务失败', 'error');
    }
  };

  const handleGenerateReplyDraft = async (thread) => {
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${thread.thread_id}/generate-reply-draft`, {}));
      const latestDraft = (data.drafts || [])[0];
      if (latestDraft) {
        setDraftForm({
          account_id: latestDraft.account_id || thread.account_id,
          to: (latestDraft.to || []).map(item => item.email).join(', '),
          cc: (latestDraft.cc || []).map(item => item.email).join(', '),
          bcc: (latestDraft.bcc || []).map(item => item.email).join(', '),
          subject: latestDraft.subject || '',
          body_html: (latestDraft.body_html || '').replace(/<br\s*\/?>/gi, '\n'),
          tone_mode: latestDraft.tone_mode || 'warm',
          signature: latestDraft.signature || activeAccount?.signature_text || '',
        });
      }
      setSelectedThreadId(thread.thread_id);
      setComposerOpen(true);
      toast(data.draft_source === 'ai' ? 'AI 已替你起草回信' : '已生成模板回信草稿', 'success');
      await refreshAll(selectedAccount, selectedFolder);
      await fetchThreadDetail(thread.thread_id);
    } catch (e) {
      toast(e.message || '生成回信草稿失败', 'error');
    }
  };

  const handlePolicyChange = async (nextPolicy) => {
    if (!activeAccount?.account_id || nextPolicy === activeAccount.auto_mail_policy) {
      return;
    }
    setPolicySaving(true);
    try {
      await request(() => apiPut(`/api/mail/accounts/${activeAccount.account_id}`, {
        auto_mail_policy: nextPolicy,
      }));
      toast(`自动处理已切到“${getAutoMailPolicyLabel(nextPolicy)}”`, 'success');
      await refreshAll(selectedAccount, selectedFolder);
      if (selectedThreadId) {
        await fetchThreadDetail(selectedThreadId);
      }
    } catch (e) {
      toast(e.message || '更新自动处理策略失败', 'error');
    } finally {
      setPolicySaving(false);
    }
  };

  const selectedThread = threadDetail?.thread || threads.find(item => item.thread_id === selectedThreadId) || null;
  const selectedAgentRuns = threadDetail?.agent_runs || [];

  const openPrevThread = () => {
    if (selectedThreadIndex > 0) {
      setSelectedThreadId(threads[selectedThreadIndex - 1].thread_id);
    }
  };

  const openNextThread = () => {
    if (selectedThreadIndex >= 0 && selectedThreadIndex < threads.length - 1) {
      setSelectedThreadId(threads[selectedThreadIndex + 1].thread_id);
    }
  };

  return (
    <div className="page-shell atlas-page-shell">
      <section className="atlas-chapter-head">
        <div>
          <div className="section-kicker">Chapter 09 / Correspondence Desk</div>
          <h1 className="atlas-chapter-title">这里不再是下载转运页，而是一张真正开始运作的书信台。</h1>
          <div className="atlas-chapter-copy">
            来信、回信、草稿、已读与归档，都不该散落在系统边缘。每一封信都应该被放回桌面中央，重新编入你的任务、记忆与今日节奏。
          </div>
        </div>
        <div className="atlas-chapter-note">
          <div className="atlas-chapter-note-title">处理顺序</div>
          <div className="atlas-chapter-note-copy">先看今天有多少封信需要回应，再读最紧要的那一封，最后安静地把回信写完寄出。</div>
        </div>
      </section>

      <section className="mission-masthead atlas-leaf">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">LETTER ROOM</span>
            <h1 className="mission-title">书信台该像一张有来有往的案桌，而不是一堵冷冰冰的消息墙。</h1>
            <div className="mission-copy">
              如果今天有信抵达，你会在这里看见它们的来处、语气、等待和重量。若要回信，也不必匆忙，只要先把最重要的一封翻开。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-warning">{dashboard?.inbound_today ?? 0} 封今日来信</span>
              <span className="badge badge-error">{dashboard?.needs_reply_threads ?? 0} 条待回应线程</span>
              <span className="badge badge-pending">{dashboard?.waiting_decision_threads ?? 0} 封待你决定</span>
              <span className="badge badge-pending">{dashboard?.draft_count ?? 0} 份草稿</span>
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">通信气候</div>
            <div className="mission-sidecard-copy">
              清晰永远先于修辞，但一封体面的信仍然值得有温度。你可以让它克制，也可以让它像月光下写成的短笺。
            </div>
          </div>
        </div>
      </section>

      <div className="atlas-toolbar">
        <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)} style={{ maxWidth: 220 }}>
          <option value="">全部账户</option>
          {accounts.map(account => (
            <option key={account.account_id} value={account.account_id}>{account.display_name} · {account.email_address}</option>
          ))}
        </select>
        <select value={selectedFolder} onChange={(e) => setSelectedFolder(e.target.value)} style={{ maxWidth: 160 }}>
          {FOLDER_OPTIONS.map(option => (
            <option key={option.value || 'all'} value={option.value}>{option.label}</option>
          ))}
        </select>
        <button className="btn btn-ghost" onClick={handleSyncInbox} disabled={!selectedAccount || syncing || loading}>
          {syncing ? '正在拉信…' : '同步收件箱'}
        </button>
        <select
          value={activeAccount?.auto_mail_policy || 'draft_and_notify'}
          onChange={(e) => handlePolicyChange(e.target.value)}
          disabled={!activeAccount || policySaving || loading}
          style={{ maxWidth: 200 }}
        >
          {AUTO_MAIL_POLICY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <div className="board-toolbar-spacer" />
        <button className="btn btn-ghost" onClick={() => onOpenNotifyNetwork?.()}>账户接线</button>
        <button className="btn btn-primary" onClick={() => setComposerOpen(true)}>写一封信</button>
      </div>

      <div className="board-summary-grid">
        <div className="board-summary-card">
          <div className="board-summary-label">活跃线程</div>
          <div className="board-summary-value">{dashboard?.total_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">未读线程</div>
          <div className="board-summary-value">{dashboard?.unread_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">待回信</div>
          <div className="board-summary-value">{dashboard?.needs_reply_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">待你决定</div>
          <div className="board-summary-value">{dashboard?.waiting_decision_threads ?? 0}</div>
        </div>
        <div className="board-summary-card">
          <div className="board-summary-label">最近同步</div>
          <div className="board-summary-value" style={{ fontSize: '1rem' }}>
            {syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : '尚未拉信'}
          </div>
        </div>
      </div>

      {activeAccount && (
        <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">AUTO HANDLER</div>
              <h3 className="board-lane-title">自动回信策略</h3>
              <div className="board-lane-copy">
                当前账户「{activeAccount.display_name}」采用“{getAutoMailPolicyLabel(activeAccount.auto_mail_policy)}”。
                这是书信代理的行事准则，决定它在手机端来信抵达后，是只起草、等你确认，还是直接替你寄出。
              </div>
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">{activeAccount.email_address}</span>
              <span className="badge badge-warning">{getAutoMailPolicyLabel(activeAccount.auto_mail_policy)}</span>
            </div>
          </div>
          <div className="signal-row" style={{ marginTop: 'var(--space-md)', alignItems: 'flex-start' }}>
            <div>
              <div className="signal-row-title">当前行为说明</div>
              <div className="signal-row-copy">{getAutoPolicyNarrative(activeAccount.auto_mail_policy)}</div>
            </div>
            <button className="btn btn-sm btn-ghost" onClick={() => onOpenNotifyNetwork?.()}>去接线检定页调整</button>
          </div>
        </section>
      )}

      {decisionQueue.length > 0 && (
        <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
          <div className="board-lane-header">
            <div>
              <div className="section-kicker">DECISION QUEUE</div>
              <h3 className="board-lane-title">待你决定</h3>
              <div className="board-lane-copy">有些信不该被立刻埋进归档。它们像黄昏时分的敲门声，等你决定是回信、安排，还是让它稍后再来。</div>
            </div>
          </div>
          <div className="board-card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
            {decisionQueue.slice(0, 6).map(thread => (
              <DecisionQueueCard
                key={thread.thread_id}
                thread={thread}
                onOpen={setSelectedThreadId}
                onDiscuss={handleDiscussWithAi}
                onCreateTask={handleCreateTaskFromMail}
              />
            ))}
          </div>
        </section>
      )}

      <div className="war-room-grid mail-spread-grid">
        <div className="war-room-stack">
          <section className="board-lane atlas-paper-stack mail-spread-lane mail-rail-lane">
            <div className="board-lane-header mail-lane-header">
              <div className="mail-lane-head-copy">
                <div className="section-kicker">INBOX RAIL</div>
                <h3 className="board-lane-title">{selectedFolder === 'archive' ? '归档箱' : '来信匣'}</h3>
                <div className="board-lane-copy">
                  {selectedFolder === 'archive'
                    ? '归档箱不再维持工作流姿势，只保留一份安静的历史索引。你可以按时间翻检，但它们不该继续抢占案头。'
                    : '这里改成像游戏里的选卡台。一次只看一封活跃线程，用上一封和下一封慢慢翻，不让长列表把注意力拖散。'}
                </div>
              </div>
              <div className="mail-lane-status">
                <div className="mail-lane-status-label">{selectedFolder === 'archive' ? '历史索引' : '翻页进度'}</div>
                <div className="mail-lane-status-value">
                  {threads.length === 0
                    ? '暂无线程'
                    : (selectedFolder === 'archive'
                      ? `${threads.length} 封已归档`
                      : `第 ${Math.max(selectedThreadIndex + 1, 1)} / ${threads.length} 封`)}
                </div>
                <div className="mail-lane-status-copy">
                  {selectedFolder === 'archive'
                    ? '这些信只供回看，不继续占用当前工作台。'
                    : '每次只翻一张卡，让注意力停在正在处理的那封来信上。'}
                </div>
              </div>
            </div>

            {threads.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✉️</div>
                <div className="empty-state-text">案头还没有信</div>
                <div className="empty-state-hint">先接一个邮箱账户，或者从系统里写出第一封信。</div>
              </div>
            ) : (
              selectedFolder === 'archive' ? (
                <div className="signal-list mail-archive-list">
                  {threads.map(thread => (
                    <ArchiveThreadRow
                      key={thread.thread_id}
                      thread={thread}
                      active={thread.thread_id === selectedThreadId}
                      onOpen={setSelectedThreadId}
                    />
                  ))}
                </div>
              ) : (
                <div className="mail-rail-body">
                  <div className="mail-rail-toolbar">
                    <div className="mail-rail-toolbar-copy">
                      活跃线程不会再拉成长长一列，而是像牌桌上一张张翻开。
                    </div>
                    <div className="inline-actions">
                      <button className="btn btn-sm btn-ghost" onClick={openPrevThread} disabled={selectedThreadIndex <= 0}>上一封</button>
                      <button className="btn btn-sm btn-ghost" onClick={openNextThread} disabled={selectedThreadIndex < 0 || selectedThreadIndex >= threads.length - 1}>下一封</button>
                    </div>
                  </div>

                  {railThread && (
                    <div className="mail-thread-stage">
                      <ThreadCard
                        key={railThread.thread_id}
                        thread={railThread}
                        active={railThread.thread_id === selectedThreadId}
                        onOpen={setSelectedThreadId}
                      />
                    </div>
                  )}

                  {threads.length > 1 && (
                    <div className="mail-rail-pagination">
                      {threads.map((thread, index) => (
                        <button
                          key={thread.thread_id}
                          type="button"
                          className={`badge ${thread.thread_id === selectedThreadId ? 'badge-warning' : 'badge-ghost'}`}
                          onClick={() => setSelectedThreadId(thread.thread_id)}
                          style={{ cursor: 'pointer' }}
                          title={thread.subject}
                        >
                          {index + 1}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )
            )}
          </section>
        </div>

        <div className="war-room-stack">
          <section className="board-lane atlas-ledger-lane mail-spread-lane mail-letter-lane">
            <div className="board-lane-header mail-lane-header">
              <div className="mail-lane-head-copy">
                <div className="section-kicker">OPEN LETTER</div>
                <h3 className="board-lane-title">{selectedThread?.subject || '当前没有展开的信'}</h3>
                <div className="board-lane-copy">
                  {selectedThread
                    ? (selectedThread.latest_folder_kind === 'archive'
                      ? '这是一条已经归档的往来记录。这里更适合翻阅、回看和确认历史，而不是继续把它摆在当前工作流正中央。'
                      : `最近收在 ${getInboxLabel(selectedThread.latest_folder_kind)}，${selectedThread.needs_reply ? '仍在等待你的回信。' : '这条往返已经暂时安静下来。'}`)
                    : '当你翻开一条线程，它会在这里展开成一叠真正可以阅读的往返信件。'}
                </div>
              </div>
              <div className="mail-lane-status">
                <div className="mail-lane-status-label">展开状态</div>
                <div className="mail-lane-status-value">
                  {selectedThread ? formatDateTime(selectedThread.latest_message_at) : '等待翻开'}
                </div>
                <div className="mail-lane-status-copy">
                  {selectedThread
                    ? (selectedThread.latest_folder_kind === 'archive'
                      ? '这是一条已归档往来，适合回看与确认历史。'
                      : (selectedThread.needs_reply ? '这封信仍在等待你的下一步回应。' : '这条往返已暂时安静，但仍可继续处理。'))
                    : '先从左侧翻开一封信，右页才会真正亮起来。'}
                </div>
              </div>
            </div>
            <div className="mail-letter-annotations">
              {!selectedThread && selectedFolder !== 'archive' && (
                <div className="mail-letter-note">
                  默认只展示仍在流动的活跃线程。已归档的信不会继续占住案头，要看它们请切到归档箱。
                </div>
              )}
              {selectedThread?.portal_url && (
                <div className="mail-letter-note">
                  这封信也有一张可从邮件里直接点开的处理页。桌面端和邮件端现在走的是同一条入口，不再是两套说法。
                </div>
              )}
              {!!selectedThread?.linked_task_count && (
                <div className="mail-letter-note">
                  这封信已经牵出 {selectedThread.linked_task_count} 项任务，纸页之外，事情已经开始移动。
                </div>
              )}
              {selectedThread?.last_actor && (
                <div className="mail-letter-note">
                  当前往返停在
                  {selectedThread.last_actor === 'counterparty' ? '对方' : selectedThread.last_actor === 'self' ? '我方' : '空白'}
                  一侧；
                  {selectedThread.has_new_inbound ? '有新的入站来信尚未闭环。' : '最近一轮往返已经暂时闭合。'}
                  {selectedThread.has_pending_draft ? '案头还有一份待发草稿。' : '当前没有挂起草稿。'}
                </div>
              )}
            </div>
            {selectedThread && (
              <div className="mail-letter-toolbar">
                <div>
                  <div className="section-kicker">MAIL-FIRST ENTRY</div>
                  <div className="inline-actions" style={{ marginTop: 8 }}>
                    <button className="btn btn-sm btn-primary" onClick={() => openPortalPage(selectedThread)}>打开处理页</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => copyPortalLink(selectedThread)}>复制处理页链接</button>
                  </div>
                </div>

                <div>
                  <div className="section-kicker">DESKTOP ACTIONS</div>
                  <div className="inline-actions" style={{ marginTop: 8 }}>
                    {!!selectedThread.unread_count && <button className="btn btn-sm btn-ghost" onClick={() => handleMarkRead(selectedThread.thread_id)}>标记已读</button>}
                    {selectedThread.latest_folder_kind !== 'archive' && <button className="btn btn-sm btn-ghost" onClick={() => handleArchive(selectedThread.thread_id)}>归档</button>}
                    {selectedThread.waiting_user_decision && <button className="btn btn-sm btn-ghost" onClick={() => handleDecisionStatus(selectedThread.thread_id, 'snoozed')}>稍后再问</button>}
                    {selectedThread.waiting_user_decision && <button className="btn btn-sm btn-ghost" onClick={() => handleDecisionStatus(selectedThread.thread_id, 'cleared')}>暂时处理完</button>}
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={() => {
                        setComposerOpen(true);
                        const latestInbound = (threadDetail?.messages || []).filter(item => item.direction === 'inbound').slice(-1)[0];
                        setDraftForm(prev => ({
                          ...prev,
                          account_id: selectedThread.account_id,
                          subject: selectedThread.subject.startsWith('Re:') ? selectedThread.subject : `Re: ${selectedThread.subject}`,
                          to: latestInbound?.from_email || '',
                          signature: activeAccount?.signature_text || prev.signature,
                        }));
                      }}
                    >
                      回复这封信
                    </button>
                    <button className="btn btn-sm btn-ghost" onClick={() => handleGenerateReplyDraft(selectedThread)}>一键起草</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => handleCreateTaskFromMail(selectedThread)}>转成任务</button>
                    <button className="btn btn-sm btn-ghost" onClick={() => handleDiscussWithAi(selectedThread)}>和 AI 商量</button>
                  </div>
                </div>
              </div>
            )}

            {!selectedThread || !threadDetail ? (
              <div className="empty-state">
                <div className="empty-state-icon">🕯️</div>
                <div className="empty-state-text">先从左侧选一封信</div>
                <div className="empty-state-hint">最值得先翻开的，通常是那条还亮着未读或待回标记的线程。</div>
              </div>
            ) : (
              <div className="board-card-grid mail-letter-stack" style={{ gridTemplateColumns: '1fr' }}>
                {selectedAgentRuns.length > 0 && (
                  <article className="dossier-card" style={{ transform: 'rotate(0.25deg)', borderColor: 'var(--accent)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                      <div>
                        <div className="section-kicker">AGENT LEDGER</div>
                        <h3 className="dossier-title">自动处理台账</h3>
                        <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                          系统替你起草、跳过、等待确认或自动寄出的动作，都会在这里留下痕迹。
                        </div>
                      </div>
                      <span className="badge badge-ghost">{selectedAgentRuns.length} 条记录</span>
                    </div>
                    <div className="signal-list" style={{ marginTop: 'var(--space-md)' }}>
                      {selectedAgentRuns.map((run) => (
                        <div key={run.run_id} className="signal-row" style={{ alignItems: 'flex-start' }}>
                          <div>
                            <div className="signal-row-title">
                              {run.action_kind === 'auto_reply' ? '自动回信代理' : run.action_kind}
                            </div>
                            <div className="signal-row-copy">
                              {run.result_summary || '系统已记录这一轮自动处理。'}
                            </div>
                            {!!run.details?.reason_code && (
                              <div className="signal-row-copy" style={{ marginTop: 6 }}>
                                {getAgentRunReasonLabel(run.details.reason_code) || run.details.reason_code}
                                {run.details?.policy ? ` · 策略 ${getAutoMailPolicyLabel(run.details.policy)}` : ''}
                              </div>
                            )}
                            <div className="signal-row-copy" style={{ marginTop: 6 }}>
                              {formatDateTime(run.updated_at || run.created_at)}
                            </div>
                          </div>
                          <span className={`badge ${getAgentRunStatusBadge(run.status)}`}>{getAgentRunStatusLabel(run.status)}</span>
                        </div>
                      ))}
                    </div>
                  </article>
                )}
                {(threadDetail.messages || []).map(message => (
                  <MessagePaper key={message.message_id} message={message} />
                ))}
                {(threadDetail.drafts || []).filter(draft => draft.status !== 'sent').map(draft => (
                  <article key={draft.draft_id} className="dossier-card" style={{ transform: 'rotate(-0.2deg)', borderColor: 'var(--warning)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--space-sm)', alignItems: 'flex-start' }}>
                      <div>
                        <div className="section-kicker">草稿席</div>
                        <h3 className="dossier-title">{draft.subject}</h3>
                      </div>
                      <span className="badge badge-pending">{draft.status === 'queued' ? '待寄出' : '草稿'}</span>
                    </div>
                    <div style={{ marginTop: 10, whiteSpace: 'pre-wrap', fontSize: '0.92rem', lineHeight: 1.65 }}>
                      {draft.body_html || '这份草稿还没有正文。'}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>

      {composerOpen && (
        <div className="modal-overlay" onClick={() => setComposerOpen(false)}>
          <div className="modal atlas-paper-stack" style={{ width: 'min(840px, 92vw)', maxHeight: '88vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div className="board-lane-header" style={{ marginBottom: 'var(--space-lg)' }}>
              <div>
                <div className="section-kicker">WRITING DESK</div>
                <h3 className="board-lane-title">写一封信</h3>
                <div className="board-lane-copy">先把事实写清楚，再决定是让它温和，还是让它保留一点夜色与纸页的气息。</div>
              </div>
            </div>

            <form onSubmit={handleComposeSubmit} className="command-form">
              <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: 'var(--space-md)' }}>
                <div className="form-group">
                  <label>发信账户</label>
                  <select value={draftForm.account_id} onChange={(e) => setDraftForm(prev => ({ ...prev, account_id: e.target.value }))}>
                    <option value="">请选择账户</option>
                    {accounts.map(account => (
                      <option key={account.account_id} value={account.account_id}>{account.display_name} · {account.email_address}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>语气</label>
                  <select value={draftForm.tone_mode} onChange={(e) => setDraftForm(prev => ({ ...prev, tone_mode: e.target.value }))}>
                    {TONE_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>收件人</label>
                <input value={draftForm.to} onChange={(e) => setDraftForm(prev => ({ ...prev, to: e.target.value }))} placeholder="reader@example.com, friend@example.com" />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
                <div className="form-group">
                  <label>抄送</label>
                  <input value={draftForm.cc} onChange={(e) => setDraftForm(prev => ({ ...prev, cc: e.target.value }))} placeholder="cc@example.com" />
                </div>
                <div className="form-group">
                  <label>密送</label>
                  <input value={draftForm.bcc} onChange={(e) => setDraftForm(prev => ({ ...prev, bcc: e.target.value }))} placeholder="bcc@example.com" />
                </div>
              </div>

              <div className="form-group">
                <label>主题</label>
                <input value={draftForm.subject} onChange={(e) => setDraftForm(prev => ({ ...prev, subject: e.target.value }))} placeholder="写给黄昏前的答复" />
              </div>

              <div className="form-group">
                <label>正文</label>
                <textarea
                  value={draftForm.body_html}
                  onChange={(e) => setDraftForm(prev => ({ ...prev, body_html: e.target.value }))}
                  placeholder={draftForm.tone_mode === 'romantic'
                    ? '先把要说清楚的事情落在纸上，再让语气慢一点，轻一点。'
                    : '请清晰写出事实、请求与下一步。'}
                  style={{ minHeight: 220 }}
                />
              </div>

              <div className="form-group">
                <label>署名</label>
                <textarea value={draftForm.signature} onChange={(e) => setDraftForm(prev => ({ ...prev, signature: e.target.value }))} style={{ minHeight: 90 }} />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setComposerOpen(false)}>收起信纸</button>
                <button type="submit" className="btn btn-primary" disabled={loading}>寄出这封信</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
