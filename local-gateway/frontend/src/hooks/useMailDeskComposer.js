import { useCallback, useState } from 'react';
import { apiGet, apiPost, apiPut } from './useApi';
import { createComposerStateFromDraft } from '../components/maildesk/maildeskShared.jsx';

const EMPTY_DRAFT_FORM = {
  account_id: '',
  to: '',
  cc: '',
  bcc: '',
  subject: '',
  body_html: '',
  tone_mode: 'warm',
  signature: '',
  scheduled_send_at: '',
};

const EMPTY_TASK_DRAFT_FORM = {
  task_name: '',
  due_time: '',
  priority: 2,
  description: '',
};

export function useMailDeskComposer({
  request,
  toast,
  activeAccount,
  activeDraft,
  selectedFolder,
  selectedThread,
  selectedThreadId,
  threadDetail,
  taskComposerThreadId,
  setTaskComposerThreadId,
  taskComposerThread,
  refreshDeskSnapshot,
  fetchDashboard,
  syncThreadDetailIntoDesk,
  setSelectedThreadId,
  setThreadDetail,
  createTaskDraftFromThread,
}) {
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerDraftId, setComposerDraftId] = useState('');
  const [composerThreadId, setComposerThreadId] = useState('');
  const [composerResetting, setComposerResetting] = useState(false);
  const [composerSaving, setComposerSaving] = useState(false);
  const [composerSending, setComposerSending] = useState(false);
  const [taskComposerOpen, setTaskComposerOpen] = useState(false);
  const [taskCreatingThreadId, setTaskCreatingThreadId] = useState('');
  const [draftForm, setDraftForm] = useState(EMPTY_DRAFT_FORM);
  const [taskDraftForm, setTaskDraftForm] = useState(EMPTY_TASK_DRAFT_FORM);

  const resetComposer = useCallback(() => {
    setComposerDraftId('');
    setComposerThreadId('');
    setDraftForm((prev) => ({
      ...prev,
      account_id: activeAccount?.account_id || prev.account_id,
      to: '',
      cc: '',
      bcc: '',
      subject: '',
      body_html: '',
      tone_mode: activeAccount?.tone_mode || 'warm',
      signature: activeAccount?.signature_text || '',
      scheduled_send_at: '',
    }));
  }, [activeAccount]);

  const hydrateComposerFromDraft = useCallback((draft, thread = null) => {
    setComposerDraftId(draft?.draft_id || '');
    setComposerThreadId(draft?.thread_id || thread?.thread_id || '');
    setDraftForm(createComposerStateFromDraft(draft, thread, activeAccount));
  }, [activeAccount]);

  const openDraftComposer = useCallback((draft, thread = null) => {
    hydrateComposerFromDraft(draft, thread);
    setComposerOpen(true);
  }, [hydrateComposerFromDraft]);

  const openBlankComposer = useCallback(() => {
    resetComposer();
    setComposerOpen(true);
  }, [resetComposer]);

  const openTaskComposer = useCallback((thread) => {
    if (!thread?.thread_id) {
      toast('当前没有可落成任务的邮件线程', 'warning');
      return;
    }
    setTaskComposerThreadId(thread.thread_id);
    setTaskDraftForm(createTaskDraftFromThread(thread));
    setTaskComposerOpen(true);
  }, [createTaskDraftFromThread, toast]);

  const parseRecipientLine = useCallback((value) => {
    return value
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean)
      .map((email) => ({ email, name: email.split('@')[0] || email }));
  }, []);

  const createDraftPayload = useCallback(() => ({
    account_id: draftForm.account_id,
    subject: draftForm.subject.trim(),
    body_html: draftForm.body_html.trim().replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\n/g, '<br>'),
    to: parseRecipientLine(draftForm.to),
    cc: parseRecipientLine(draftForm.cc),
    bcc: parseRecipientLine(draftForm.bcc),
    thread_id: composerThreadId || undefined,
    tone_mode: draftForm.tone_mode,
    signature: draftForm.signature,
    scheduled_send_at: draftForm.scheduled_send_at ? new Date(draftForm.scheduled_send_at).toISOString() : null,
    user_edited_after_ai: true,
  }), [composerThreadId, draftForm, parseRecipientLine]);

  const ensureDraftSaved = useCallback(async () => {
    const payload = createDraftPayload();
    if (composerDraftId) {
      const updated = await request(() => apiPut(`/api/mail/drafts/${composerDraftId}`, payload));
      const nextThreadId = updated.thread?.thread_id || updated.thread_id || composerThreadId;
      setComposerThreadId(nextThreadId || '');
      return { draft_id: composerDraftId, thread_id: nextThreadId };
    }

    const created = await request(() => apiPost('/api/mail/drafts', payload));
    setComposerDraftId(created.draft_id || '');
    setComposerThreadId(created.thread_id || '');
    return { draft_id: created.draft_id, thread_id: created.thread_id };
  }, [composerDraftId, composerThreadId, createDraftPayload, request]);

  const handleComposeSubmit = useCallback(async (e) => {
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
    setComposerSending(true);
    try {
      const draft = await ensureDraftSaved();
      await request(() => apiPost(`/api/mail/drafts/${draft.draft_id}/send`, {}));
      toast('信已经寄出', 'success');
      setComposerOpen(false);
      resetComposer();
      await refreshDeskSnapshot(draftForm.account_id, selectedFolder);
      setSelectedThreadId(draft.thread_id);
    } catch (error) {
      toast(error.message || '寄信失败', 'error');
    } finally {
      setComposerSending(false);
    }
  }, [draftForm.account_id, draftForm.subject, draftForm.to, ensureDraftSaved, refreshDeskSnapshot, request, resetComposer, selectedFolder, setSelectedThreadId, toast]);

  const handleSaveDraftOnly = useCallback(async () => {
    if (!draftForm.account_id) {
      toast('请先选择一个书信账户', 'warning');
      return;
    }
    if (!draftForm.subject.trim()) {
      toast('请填写主题', 'warning');
      return;
    }
    setComposerSaving(true);
    try {
      const draft = await ensureDraftSaved();
      toast(composerDraftId ? '草稿已经更新' : '草稿已经放回案头', 'success');
      if (draft.thread_id) {
        setSelectedThreadId(draft.thread_id);
        const detail = await apiGet(`/api/mail/threads/${draft.thread_id}`);
        syncThreadDetailIntoDesk(detail);
        await fetchDashboard(draftForm.account_id);
      }
    } catch (error) {
      toast(error.message || '保存草稿失败', 'error');
    } finally {
      setComposerSaving(false);
    }
  }, [composerDraftId, draftForm.account_id, draftForm.subject, ensureDraftSaved, fetchDashboard, setSelectedThreadId, syncThreadDetailIntoDesk, toast]);

  const handleCreateTaskFromMail = useCallback(async (thread) => {
    openTaskComposer(thread);
  }, [openTaskComposer]);

  const handleSubmitTaskFromMail = useCallback(async (e) => {
    e?.preventDefault?.();
    if (!taskComposerThread?.thread_id) {
      toast('当前没有可关联的邮件线程', 'warning');
      return;
    }
    if (!taskDraftForm.task_name.trim()) {
      toast('请先写下任务标题', 'warning');
      return;
    }
    setTaskCreatingThreadId(taskComposerThread.thread_id);
    try {
      const data = await request(() => apiPost(`/api/mail/threads/${taskComposerThread.thread_id}/create-task`, {
        task_name: taskDraftForm.task_name.trim(),
        due_time: taskDraftForm.due_time ? new Date(taskDraftForm.due_time).toISOString() : null,
        description: taskDraftForm.description.trim(),
        priority: Number(taskDraftForm.priority),
      }));
      toast(`已落成任务：${data.task_name}`, 'success');
      syncThreadDetailIntoDesk(data, { removeWhenFilteredOut: false });
      setTaskComposerOpen(false);
      setTaskComposerThreadId('');
    } catch (error) {
      toast(error.message || '从邮件创建任务失败', 'error');
    } finally {
      setTaskCreatingThreadId('');
    }
  }, [request, syncThreadDetailIntoDesk, taskComposerThread, taskDraftForm, toast]);

  const handleReplyThread = useCallback((thread) => {
    if (!thread) {
      return;
    }
    if (activeDraft) {
      openDraftComposer(activeDraft, thread);
      return;
    }
    resetComposer();
    setComposerThreadId(thread.thread_id);
    setComposerOpen(true);
    const latestInbound = (threadDetail?.messages || []).filter((item) => item.direction === 'inbound').slice(-1)[0];
    setDraftForm((prev) => ({
      ...prev,
      account_id: thread.account_id,
      subject: thread.subject.startsWith('Re:') ? thread.subject : `Re: ${thread.subject}`,
      to: latestInbound?.from_email || '',
      signature: activeAccount?.signature_text || prev.signature,
    }));
  }, [activeAccount, activeDraft, openDraftComposer, resetComposer, threadDetail]);

  const handleResetComposerToLatestDraft = useCallback(async () => {
    const threadId = composerThreadId || selectedThreadId;
    if (!composerDraftId || !threadId) {
      toast('当前没有可回退的已保存草稿', 'warning');
      return;
    }
    setComposerResetting(true);
    try {
      const data = await request(() => apiGet(`/api/mail/threads/${threadId}`));
      const latestDraft = (data.drafts || []).find((draft) => draft.status !== 'sent' && draft.draft_id === composerDraftId)
        || (data.drafts || []).find((draft) => draft.status !== 'sent');
      if (!latestDraft) {
        toast('服务器上已经没有这份待发草稿了', 'warning');
        return;
      }
      setThreadDetail((prev) => (prev?.thread?.thread_id === threadId ? data : prev));
      hydrateComposerFromDraft(latestDraft, data.thread || selectedThread);
      toast('已回到服务器上的最新草稿版本', 'success');
    } catch (error) {
      toast(error.message || '重置草稿失败', 'error');
    } finally {
      setComposerResetting(false);
    }
  }, [composerDraftId, composerThreadId, hydrateComposerFromDraft, request, selectedThread, selectedThreadId, setThreadDetail, toast]);

  return {
    composerOpen,
    setComposerOpen,
    composerDraftId,
    composerThreadId,
    composerResetting,
    composerSaving,
    composerSending,
    taskComposerOpen,
    setTaskComposerOpen,
    taskComposerThreadId,
    taskCreatingThreadId,
    draftForm,
    setDraftForm,
    taskDraftForm,
    setTaskDraftForm,
    resetComposer,
    hydrateComposerFromDraft,
    openDraftComposer,
    openBlankComposer,
    openTaskComposer,
    handleComposeSubmit,
    handleSaveDraftOnly,
    handleCreateTaskFromMail,
    handleSubmitTaskFromMail,
    handleReplyThread,
    handleResetComposerToLatestDraft,
  };
}
