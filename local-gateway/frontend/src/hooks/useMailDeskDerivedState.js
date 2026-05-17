import { useCallback, useMemo } from 'react';
import {
  buildMailtoReplyLink,
  getMailKindLabel,
  getReplyLevelLabel,
} from '../components/maildesk/maildeskShared.jsx';

export function useMailDeskDerivedState({
  accounts,
  threads,
  threadDetail,
  activeDraft,
  agentRunFilter,
  selectedThreadId,
  taskComposerThreadId,
  onOpenAi,
  setSelectedThreadId,
}) {
  const selectedAgentRuns = useMemo(() => {
    const runs = threadDetail?.agent_runs || [];
    if (agentRunFilter === 'all') return runs;
    return runs.filter((run) => run.status === agentRunFilter);
  }, [agentRunFilter, threadDetail]);

  const decisionQueue = useMemo(
    () => threads.filter((item) => item.waiting_user_decision && item.latest_folder_kind !== 'archive'),
    [threads],
  );

  const selectedThreadIndex = useMemo(
    () => threads.findIndex((item) => item.thread_id === selectedThreadId),
    [threads, selectedThreadId],
  );

  const railThread = useMemo(
    () => threads[selectedThreadIndex >= 0 ? selectedThreadIndex : 0] || null,
    [selectedThreadIndex, threads],
  );

  const selectedThread = useMemo(
    () => threadDetail?.thread || threads.find((item) => item.thread_id === selectedThreadId) || null,
    [selectedThreadId, threadDetail, threads],
  );

  const taskComposerThread = useMemo(
    () => threads.find((item) => item.thread_id === taskComposerThreadId) || (selectedThread?.thread_id === taskComposerThreadId ? selectedThread : null),
    [selectedThread, taskComposerThreadId, threads],
  );

  const selectedMailtoHref = useMemo(
    () => buildMailtoReplyLink(selectedThread, threadDetail, activeDraft),
    [activeDraft, selectedThread, threadDetail],
  );

  const selectedThreadAccount = useMemo(
    () => accounts.find((item) => item.account_id === selectedThread?.account_id) || null,
    [accounts, selectedThread],
  );

  const latestAgentRun = useMemo(
    () => (threadDetail?.agent_runs || [])[0] || null,
    [threadDetail],
  );

  const handleDiscussWithAi = useCallback((thread) => {
    const latestMessage = thread.thread_id === selectedThreadId
      ? (threadDetail?.messages || []).slice(-1)[0]
      : null;
    const participants = (thread.participants || []).map((item) => item.email || item.name).filter(Boolean).join(', ');
    const summary = latestMessage?.text_body || latestMessage?.html_body || thread.snippet || '';
    onOpenAi?.({
      intent: 'mail_consult',
      thread,
      draftInput: `请作为书信参谋，帮我处理这封邮件。\n主题：${thread.subject}\n分类：${getMailKindLabel(thread.mail_kind)}\n回信强度：${getReplyLevelLabel(thread.reply_level)}\n判断理由：${thread.analysis_reason || '暂无'}\n相关参与者：${participants || '未记录'}\n邮件摘要：${summary.slice(0, 1200)}\n\n请输出：\n1. 我是否必须回复\n2. 若回复，给出建议语气与核心要点\n3. 若涉及安排，请给出任务/日程建议`,
    });
  }, [onOpenAi, selectedThreadId, threadDetail]);

  const openPrevThread = useCallback(() => {
    if (selectedThreadIndex > 0) {
      setSelectedThreadId(threads[selectedThreadIndex - 1].thread_id);
    }
  }, [selectedThreadIndex, setSelectedThreadId, threads]);

  const openNextThread = useCallback(() => {
    if (selectedThreadIndex >= 0 && selectedThreadIndex < threads.length - 1) {
      setSelectedThreadId(threads[selectedThreadIndex + 1].thread_id);
    }
  }, [selectedThreadIndex, setSelectedThreadId, threads]);

  return {
    selectedAgentRuns,
    decisionQueue,
    selectedThreadIndex,
    railThread,
    selectedThread,
    taskComposerThread,
    selectedMailtoHref,
    selectedThreadAccount,
    latestAgentRun,
    handleDiscussWithAi,
    openPrevThread,
    openNextThread,
  };
}
