import AssistantMarkdown from './AssistantMarkdown';
import { useEffect } from 'react';

const QUICK_PROMPTS = [
  {
    label: '载入今日待办',
    onClick: ({ loadPendingTasksIntoPlanning }) => loadPendingTasksIntoPlanning(),
  },
  {
    label: '今日排兵',
    onClick: ({ setInput }) => setInput('请根据当前任务草案，生成一个今天可执行、风险最低的排程建议。'),
  },
  {
    label: '风险扫描',
    onClick: ({ setInput }) => setInput('请检查当前计划中的冲突、过载点和依赖风险，并给出调整建议。'),
  },
  {
    label: '拆解任务',
    onClick: ({ setInput }) => setInput('请把一个复杂任务拆成 3-6 个今天就能推进的子任务，并标注建议时长。'),
  },
];

function ManuscriptComposer({
  inputRef,
  input,
  setInput,
  handleKeyDown,
  streaming,
  sendMessage,
  loadPendingTasksIntoPlanning,
}) {
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(220, el.scrollHeight)}px`;
  }, [inputRef, input]);

  return (
    <section className="ai-manuscript-section composer">
      <div className="ai-round-layer-label">继续写</div>
      <div className="ai-manuscript-inline-compose">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="直接在这页最后继续写下你的补充、追问或新的委托..."
          rows={1}
          className="ai-command-textarea ai-manuscript-inline-textarea"
          disabled={streaming}
        />
        <div className="ai-manuscript-inline-tools">
          <div className="ai-manuscript-inline-actions">
            {QUICK_PROMPTS.map((action) => (
              <button
                key={action.label}
                className="btn btn-sm btn-ghost"
                onClick={() => action.onClick({ setInput, loadPendingTasksIntoPlanning })}
              >
                {action.label}
              </button>
            ))}
          </div>
          <button
            className="btn btn-primary ai-manuscript-inline-submit"
            onClick={sendMessage}
            disabled={streaming || !input.trim()}
          >
            {streaming ? '誊写中...' : '落款提交'}
          </button>
        </div>
      </div>
    </section>
  );
}

function RoundToolbar({ conversationRounds, currentRoundPage, setCurrentRoundPage }) {
  if (!conversationRounds.length) return null;

  return (
    <div className="ai-round-page-toolbar">
      <div className="ai-round-page-counter">
        第 {currentRoundPage + 1} / {conversationRounds.length} 页
      </div>
      <div className="ai-round-page-dots">
        {conversationRounds.map((round) => (
          <button
            key={round.id}
            type="button"
            className={`ai-round-page-dot ${round.index - 1 === currentRoundPage ? 'active' : ''}`}
            onClick={() => setCurrentRoundPage(round.index - 1)}
            aria-label={`查看第 ${round.index} 回合`}
          />
        ))}
      </div>
      <div className="ai-round-page-actions">
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => setCurrentRoundPage((page) => Math.max(0, page - 1))}
          disabled={currentRoundPage === 0}
        >
          上一页
        </button>
        <button
          className="btn btn-sm btn-ghost"
          onClick={() => setCurrentRoundPage((page) => Math.min(conversationRounds.length - 1, page + 1))}
          disabled={currentRoundPage === conversationRounds.length - 1}
        >
          下一页
        </button>
      </div>
    </div>
  );
}

export default function AiChatManuscriptPage({
  conversationRounds,
  activeRound,
  currentRoundPage,
  setCurrentRoundPage,
  latestAssistantMessage,
  latestUserMessage,
  formatMessageStamp,
  inputRef,
  input,
  setInput,
  handleKeyDown,
  streaming,
  sendMessage,
  loadPendingTasksIntoPlanning,
  messagesEndRef,
  roundsScrollerRef,
  sidebarOpen,
  setSidebarOpen,
  showConfig,
  setShowConfig,
  currentDisplayTime,
}) {
  const displayRound = activeRound || {
    id: 'draft-round',
    index: 1,
    user: latestUserMessage || null,
    assistant: latestAssistantMessage || null,
  };
  const assistantMsg = displayRound.assistant;
  const userMsg = displayRound.user;
  const hasRoundContent = Boolean(userMsg?.content?.trim() || assistantMsg?.content?.trim());
  const showPendingAssistant = !assistantMsg || (streaming && !assistantMsg.content?.trim());

  return (
    <div className="card ai-rounds-panel">
      <div className="board-lane-header ai-book-page-header ai-manuscript-header">
        <div>
          <div className="section-kicker">Rounds</div>
          <div className="board-lane-title">回合式顾问对话</div>
          <div className="board-lane-copy">
            每次只展开一个完整回合，像翻一页参谋作战手册，而不是在长聊天流里找重点。
          </div>
        </div>
        <div className="board-toolbar">
          <button className="btn btn-ghost" onClick={() => setSidebarOpen((open) => !open)}>
            {sidebarOpen ? '收起档案夹' : '打开档案夹'}
          </button>
          <button className="btn btn-ghost" onClick={() => setShowConfig((open) => !open)}>
            {showConfig ? '收起配置' : '打开配置'}
          </button>
        </div>
      </div>

      <div ref={roundsScrollerRef} className="ai-rounds-scroller ai-manuscript-scroll">
        <RoundToolbar
          conversationRounds={conversationRounds}
          currentRoundPage={currentRoundPage}
          setCurrentRoundPage={setCurrentRoundPage}
        />

        <article key={displayRound.id} className="ai-round-page ai-manuscript-sheet">
          <div className="ai-round-page-bookmark" aria-hidden="true">
            <span />
            <span />
          </div>
          <div className="ai-round-card active large-page ai-manuscript-card">
            <div className="ai-round-card-head">
              <div>
                <div className="ai-round-number">Round {String(displayRound.index).padStart(2, '0')}</div>
                <div className="ai-round-page-title">顾问回合大页</div>
              </div>
              {hasRoundContent && (
                <div className="ai-round-meta">
                  <span>{currentDisplayTime || formatMessageStamp(userMsg?.timestamp || assistantMsg?.timestamp)}</span>
                  {assistantMsg?.tool_calls?.length ? <span>{assistantMsg.tool_calls.length} 个动作</span> : null}
                  {assistantMsg?.thinking?.trim() ? <span>含推演</span> : null}
                </div>
              )}
            </div>

            {!hasRoundContent && (
              <div className="ai-empty-stage">
                <div className="ai-empty-stage-title">还没有战术回合</div>
                <div className="ai-empty-stage-copy">
                  你可以直接提问，也可以从这页底部的快捷动作开始，让 AI 拆任务、排今日计划或扫描风险。
                </div>
              </div>
            )}

            {userMsg?.content && (
              <section className="ai-manuscript-section prompt">
                <div className="ai-round-layer-label">任务委托</div>
                <div className="ai-round-directive">{userMsg.content}</div>
              </section>
            )}

            {assistantMsg?.content?.trim() ? (
              <section className="ai-manuscript-section response">
                <div className="ai-round-layer-label">参谋回报</div>
                <div className="ai-manuscript-body">
                  <AssistantMarkdown
                    content={assistantMsg.content}
                    streaming={streaming && activeRound?.assistant?.id === assistantMsg.id}
                  />
                </div>
              </section>
            ) : showPendingAssistant && hasRoundContent ? (
              <div className="ai-round-layer assistant pending">
                <div className="ai-round-layer-label">参谋回报</div>
                <div className="ai-typing-card">
                  <span />
                  <span />
                  <span />
                  <strong>{streaming ? 'AI 正在组织回报' : '等待 AI 回应'}</strong>
                </div>
              </div>
            ) : null}

            <ManuscriptComposer
              inputRef={inputRef}
              input={input}
              setInput={setInput}
              handleKeyDown={handleKeyDown}
              streaming={streaming}
              sendMessage={sendMessage}
              loadPendingTasksIntoPlanning={loadPendingTasksIntoPlanning}
            />
          </div>
        </article>

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
