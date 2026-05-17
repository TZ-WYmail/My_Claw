import { useEffect, useMemo, useState } from 'react';

export default function MailComposerModal({
  open,
  onClose,
  onSubmit,
  composerDraftId,
  composerThreadId,
  composerResetting,
  activeDraft,
  composerSaving,
  composerSending,
  draftForm,
  setDraftForm,
  accounts,
  toneOptions,
  onResetToLatestDraft,
  onSaveDraftOnly,
}) {
  const [sendReviewOpen, setSendReviewOpen] = useState(false);
  const composerBusy = composerSaving || composerSending;

  const recipientSummary = useMemo(() => {
    return {
      to: draftForm.to.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
      cc: draftForm.cc.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
      bcc: draftForm.bcc.split(/[,\n]/).map((item) => item.trim()).filter(Boolean),
    };
  }, [draftForm.bcc, draftForm.cc, draftForm.to]);

  useEffect(() => {
    if (!open) {
      setSendReviewOpen(false);
    }
  }, [open]);

  useEffect(() => {
    setSendReviewOpen(false);
  }, [composerDraftId, composerThreadId]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal atlas-paper-stack" style={{ width: 'min(840px, 92vw)', maxHeight: '88vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
        <div className="board-lane-header" style={{ marginBottom: 'var(--space-lg)' }}>
          <div>
            <div className="section-kicker">WRITING DESK</div>
            <h3 className="board-lane-title">写一封信</h3>
            <div className="board-lane-copy">先把事实写清楚，再决定是让它温和，还是让它保留一点夜色与纸页的气息。</div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="command-form">
          <div className="mail-composer-state">
            <span className="badge badge-ghost">{composerDraftId ? '正在编辑现有草稿' : '新草稿'}</span>
            <span className="badge badge-ghost">{composerThreadId ? '已挂在线程内' : '独立发信'}</span>
            {activeDraft?.ai_generated && <span className="badge badge-warning">AI 起草</span>}
            {activeDraft?.user_edited_after_ai && <span className="badge badge-ghost">你后来改过</span>}
            {composerResetting && <span className="badge badge-warning">正在回退草稿</span>}
          </div>
          {composerDraftId && (
            <div className="mail-inline-alert mail-inline-alert-success">
              这是一份已经落库的草稿。如果别处又改过它，可以随时回退到服务器上的最新版本。
            </div>
          )}
          {activeDraft?.status === 'failed' && (
            <div className="mail-inline-alert mail-inline-alert-error">
              这份草稿上一次发送失败了。先核对收件人与正文，再重新寄出会更稳妥。
            </div>
          )}
          {!!activeDraft?.scheduled_send_at && (
            <div className="mail-inline-alert mail-inline-alert-success">
              这份草稿记录了计划寄出时间：{activeDraft.scheduled_send_at}
            </div>
          )}
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
                {toneOptions.map(option => (
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

          <div className="form-group">
            <label>计划寄出时间</label>
            <input
              type="datetime-local"
              value={draftForm.scheduled_send_at || ''}
              onChange={(e) => setDraftForm(prev => ({ ...prev, scheduled_send_at: e.target.value }))}
            />
          </div>

          {sendReviewOpen && (
            <section className="mail-send-review">
              <div className="section-kicker">SEND REVIEW</div>
              <h4 className="mail-send-review-title">{activeDraft?.status === 'failed' ? '重新寄出前确认' : '寄出前确认'}</h4>
              <div className="mail-send-review-copy">
                信一旦寄出，就会离开案头。现在先确认对象、主题和语气没有走偏，再把它送出去。
              </div>
              <div className="mail-send-review-grid">
                <div className="mail-send-review-card">
                  <div className="mail-send-review-label">收件人</div>
                  <div className="mail-send-review-value">
                    {recipientSummary.to.length > 0 ? recipientSummary.to.join(', ') : '尚未填写'}
                  </div>
                </div>
                <div className="mail-send-review-card">
                  <div className="mail-send-review-label">抄送 / 密送</div>
                  <div className="mail-send-review-value">
                    {[recipientSummary.cc.join(', '), recipientSummary.bcc.join(', ')].filter(Boolean).join(' / ') || '无'}
                  </div>
                </div>
                <div className="mail-send-review-card">
                  <div className="mail-send-review-label">主题</div>
                  <div className="mail-send-review-value">{draftForm.subject.trim() || '尚未填写'}</div>
                </div>
                <div className="mail-send-review-card">
                  <div className="mail-send-review-label">语气</div>
                  <div className="mail-send-review-value">
                    {toneOptions.find((option) => option.value === draftForm.tone_mode)?.label || draftForm.tone_mode || '未选择'}
                  </div>
                </div>
                <div className="mail-send-review-card">
                  <div className="mail-send-review-label">计划寄出</div>
                  <div className="mail-send-review-value">{draftForm.scheduled_send_at || '立即寄出'}</div>
                </div>
              </div>
              {activeDraft?.status === 'failed' && (
                <div className="mail-inline-alert mail-inline-alert-error">
                  这是一次失败后的重试寄送。若仍失败，优先检查账户链路、收件地址与 SMTP 配置。
                </div>
              )}
            </section>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>收起信纸</button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onResetToLatestDraft}
              disabled={!composerDraftId || composerResetting || composerBusy}
            >
              {composerResetting ? '回退中…' : '回到最新草稿'}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onSaveDraftOnly} disabled={composerBusy}>
              {composerSaving ? '保存中…' : '只保存草稿'}
            </button>
            {sendReviewOpen ? (
              <>
                <button type="button" className="btn btn-ghost" onClick={() => setSendReviewOpen(false)} disabled={composerBusy}>返回继续修改</button>
                <button type="submit" className="btn btn-primary" disabled={composerBusy}>
                  {composerSending ? '寄送中…' : activeDraft?.status === 'failed' ? '确认重新寄出' : '确认寄出'}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setSendReviewOpen(true)}
                disabled={composerBusy}
              >
                {activeDraft?.status === 'failed' ? '准备重新寄出' : '准备寄出'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
