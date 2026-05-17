import { useMemo } from 'react';

export function getInboxLabel(folder) {
  if (folder === 'archive') return '已归档';
  if (folder === 'sent') return '已发出';
  if (folder === 'drafts') return '草稿';
  return '收件箱';
}

export function formatDateTime(value) {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

export function getReplyLevelLabel(level) {
  if (level === 'must_reply') return '必须回信';
  if (level === 'suggest_reply') return '建议回复';
  return '仅供阅读';
}

export function getDecisionStatusLabel(status) {
  if (status === 'snoozed') return '稍后再问';
  if (status === 'cleared') return '暂时处理完';
  return '待你决定';
}

export function getMailKindLabel(kind) {
  if (kind === 'planning') return '规划相关';
  if (kind === 'reply') return '往返信件';
  if (kind === 'marketing') return '营销订阅';
  if (kind === 'outbound') return '已发信';
  return '信息信件';
}

export function getRiskBadgeClass(level) {
  if (level === 'high') return 'badge-error';
  if (level === 'low') return 'badge-completed';
  return 'badge-warning';
}

export function getAutoMailPolicyLabel(policy) {
  if (policy === 'draft_only') return '只起草';
  if (policy === 'auto_send') return '自动寄出';
  return '起草待确认';
}

export function getMailCommandLabel(command) {
  if (command === 'create_task') return '识别为转任务意图';
  if (command === 'draft_reply') return '识别为先起草回信';
  if (command === 'archive') return '识别为归档处理';
  return '未识别到邮件指令';
}

export function getAgentRunStatusLabel(status) {
  if (status === 'draft_created') return '已起草';
  if (status === 'user_confirmation_required') return '待你确认';
  if (status === 'sent') return '已自动寄出';
  if (status === 'failed') return '执行失败';
  if (status === 'skipped_non_direct') return '跳过非直接来信';
  if (status === 'skipped') return '已跳过';
  return status || '未记录';
}

export function getAgentRunStatusBadge(status) {
  if (status === 'sent') return 'badge-completed';
  if (status === 'failed') return 'badge-error';
  if (status === 'skipped_non_direct' || status === 'skipped') return 'badge-ghost';
  return 'badge-warning';
}

export function getAgentRunReasonLabel(reasonCode) {
  if (reasonCode === 'non_direct_thread') return '判定为非直接协商来信';
  if (reasonCode === 'draft_generation_failed') return '起草阶段失败';
  if (reasonCode === 'policy_draft_only') return '策略要求只起草';
  if (reasonCode === 'policy_requires_confirmation') return '策略要求等待确认';
  if (reasonCode === 'policy_auto_send') return '策略允许自动寄出';
  if (reasonCode === 'send_failed') return '发信阶段失败';
  return '';
}

export function getAutoPolicyNarrative(policy) {
  if (policy === 'draft_only') return '来信到了先落草稿，不打扰你做最终决定。';
  if (policy === 'auto_send') return '来信一旦命中自动处理链路，代理会直接替你把回信寄出去。';
  return '来信先被起草，再回到你的案头，等你拍板。';
}

export function getExecutionBadgeClass(status) {
  if (status === 'success') return 'badge-completed';
  if (status === 'error') return 'badge-error';
  return 'badge-ghost';
}

export function getExecutionStatusLabel(status) {
  if (status === 'success') return '成功';
  if (status === 'error') return '失败';
  if (status === 'skipped') return '跳过';
  return status || '未记录';
}

export function formatMailSyncCounts(item) {
  const fetched = Number(item?.fetched_count || 0);
  const nextCount = Number(item?.new_count || 0);
  return `${fetched} 抓取 / ${nextCount} 新增`;
}

export function getPollingResultNarrative(item) {
  if (!item) return '本轮没有留下可阅读的执行细节。';
  const folderLabel = getInboxLabel(item.folder_kind || 'inbox');
  const baseMessage = item.message || `已检查 ${folderLabel}`;
  const latestUid = item.latest_uid ? ` · 停在 UID ${item.latest_uid}` : '';
  return `${baseMessage} · ${formatMailSyncCounts(item)}${latestUid}`;
}

export function getAgentRunFilterLabel(filter) {
  if (filter === 'user_confirmation_required') return '待确认';
  if (filter === 'draft_created') return '已起草';
  if (filter === 'sent') return '已寄出';
  if (filter === 'failed') return '失败';
  if (filter === 'skipped') return '已跳过';
  if (filter === 'skipped_non_direct') return '非直接来信';
  return '全部记录';
}

export function getDraftStatusLabel(status) {
  if (status === 'queued') return '待寄出';
  if (status === 'failed') return '发送失败';
  if (status === 'sent') return '已寄出';
  return '草稿';
}

export function getDraftStatusBadge(status) {
  if (status === 'failed') return 'badge-error';
  if (status === 'queued') return 'badge-warning';
  if (status === 'sent') return 'badge-completed';
  return 'badge-pending';
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

export function sanitizeMailHref(rawHref) {
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

export function sanitizeMailHtml(rawHtml) {
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

export function normalizePlainLink(rawValue) {
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

export function renderPlainTextWithLinks(text) {
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

export function createComposerStateFromDraft(draft, thread, activeAccount) {
  const scheduledSendAt = draft?.scheduled_send_at || '';
  const normalizedScheduledSendAt = scheduledSendAt
    ? String(scheduledSendAt).replace('Z', '').slice(0, 16)
    : '';
  return {
    account_id: draft?.account_id || thread?.account_id || activeAccount?.account_id || '',
    to: (draft?.to || []).map(item => item.email).join(', '),
    cc: (draft?.cc || []).map(item => item.email).join(', '),
    bcc: (draft?.bcc || []).map(item => item.email).join(', '),
    subject: draft?.subject || thread?.subject || '',
    body_html: (draft?.body_html || '').replace(/<br\s*\/?>/gi, '\n'),
    tone_mode: draft?.tone_mode || activeAccount?.tone_mode || 'warm',
    signature: draft?.signature || activeAccount?.signature_text || '',
    scheduled_send_at: normalizedScheduledSendAt,
  };
}

export function buildMailtoReplyLink(thread, detail, draft) {
  const threadSubject = draft?.subject || thread?.subject || '';
  const subject = threadSubject ? (threadSubject.startsWith('Re:') ? threadSubject : `Re: ${threadSubject}`) : '';
  const recipients = [];
  const pushRecipient = (item) => {
    const email = `${item?.email || ''}`.trim();
    if (!email || recipients.includes(email)) return;
    recipients.push(email);
  };

  (draft?.to || []).forEach(pushRecipient);
  if (recipients.length === 0) {
    const latestInbound = (detail?.messages || []).filter((item) => item.direction === 'inbound').slice(-1)[0];
    (latestInbound?.reply_to || []).forEach(pushRecipient);
    if (recipients.length === 0 && latestInbound?.from_email) {
      pushRecipient({ email: latestInbound.from_email });
    }
  }

  if (recipients.length === 0) {
    return '';
  }

  const params = new URLSearchParams();
  if (subject) {
    params.set('subject', subject);
  }
  return `mailto:${recipients.join(',')}?${params.toString()}`;
}

export function DecisionQueueCard({ thread, onOpen, onDiscuss, onCreateTask }) {
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

export function ThreadCard({ thread, active, onOpen }) {
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

export function ArchiveThreadRow({ thread, active, onOpen }) {
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

export function MessagePaper({ message }) {
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
