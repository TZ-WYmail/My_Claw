import {
  formatDateTime,
  formatMailSyncCounts,
  getAutoMailPolicyLabel,
  getExecutionBadgeClass,
  getInboxLabel,
  getPollingResultNarrative,
  getExecutionStatusLabel,
} from './maildeskShared.jsx';

export default function MailControlGrid({
  activeAccount,
  accountTestResult,
  accountTesting,
  accounts,
  handleAccountTest,
  handlePollingConfigChange,
  loading,
  pollingFeedback,
  pollingResults,
  pollingSaving,
  pollingState,
  pollingSummary,
  pollingFolderOptions,
  requestOpenNotifyNetwork,
  setPollingState,
  syncStatus,
  threadFilters,
  setThreadFilters,
  refreshDeskThreads,
  deskRefreshing,
}) {
  return (
    <section className="board-lane atlas-paper-stack" style={{ marginBottom: 'var(--space-xl)' }}>
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">MAIL CONTROL GRID</div>
          <h3 className="board-lane-title">工作台控制面</h3>
          <div className="board-lane-copy">
            把轮询、筛选、同步台账和账户链路都放回同一张桌面，而不是让你为了一个动作反复跳去设置页。
          </div>
        </div>
      </div>
      <div className="mail-control-grid">
        <article className="mail-control-card">
          <div className="section-kicker">THREAD FILTERS</div>
          <div className="mail-control-title">筛选当前案头</div>
          <div className="mail-control-copy">按是否未读、是否待回、是否待决定和关键词收窄当前来信堆，让真正需要你处理的那几封浮到最上面。</div>
          <div className="command-form mail-filter-form">
            <div className="form-group">
              <label>检索词</label>
              <input
                value={threadFilters.query}
                onChange={(e) => setThreadFilters(prev => ({ ...prev, query: e.target.value }))}
                placeholder="主题、摘要或参与者"
              />
            </div>
            <div className="mail-filter-toggles">
              <button type="button" className={`badge ${threadFilters.unreadOnly ? 'badge-warning' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, unreadOnly: !prev.unreadOnly }))}>只看未读</button>
              <button type="button" className={`badge ${threadFilters.needsReplyOnly ? 'badge-error' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, needsReplyOnly: !prev.needsReplyOnly }))}>只看待回信</button>
              <button type="button" className={`badge ${threadFilters.waitingDecisionOnly ? 'badge-pending' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, waitingDecisionOnly: !prev.waitingDecisionOnly }))}>只看待决定</button>
              <button type="button" className={`badge ${threadFilters.scheduledOnly ? 'badge-completed' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, scheduledOnly: !prev.scheduledOnly }))}>只看定时寄出</button>
              <button type="button" className={`badge ${threadFilters.failedDraftOnly ? 'badge-error' : 'badge-ghost'}`} onClick={() => setThreadFilters(prev => ({ ...prev, failedDraftOnly: !prev.failedDraftOnly }))}>只看发送失败</button>
              <button
                type="button"
                className="badge badge-ghost"
                onClick={() => setThreadFilters({
                  query: '',
                  unreadOnly: false,
                  needsReplyOnly: false,
                  waitingDecisionOnly: false,
                  scheduledOnly: false,
                  failedDraftOnly: false,
                })}
              >
                清空筛选
              </button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={refreshDeskThreads} disabled={deskRefreshing}>
                {deskRefreshing ? '案头刷新中…' : '刷新案头'}
              </button>
            </div>
          </div>
        </article>

        <article className="mail-control-card">
          <div className="section-kicker">POLLING DESK</div>
          <div className="mail-control-title">后台拉信轮询</div>
          <div className="mail-control-copy">系统现在可以按固定节奏主动去邮箱看信，而不是只在你点按钮时才醒来。</div>
          <div className="mail-polling-grid">
            <label className="mail-toggle-row">
              <span>轮询开关</span>
              <input
                type="checkbox"
                checked={!!pollingState.enabled}
                disabled={pollingSaving || loading}
                onChange={(e) => handlePollingConfigChange({ enabled: e.target.checked })}
              />
            </label>
            <div className="form-group">
              <label>轮询信箱</label>
              <select
                value={pollingState.folder_kind || 'inbox'}
                disabled={pollingSaving || loading}
                onChange={(e) => handlePollingConfigChange({ folder_kind: e.target.value })}
              >
                {pollingFolderOptions.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>间隔秒数</label>
              <input
                type="number"
                min={60}
                max={86400}
                value={pollingState.interval_seconds || 300}
                disabled={pollingSaving || loading}
                onChange={(e) => setPollingState(prev => ({ ...prev, interval_seconds: e.target.value }))}
                onBlur={() => handlePollingConfigChange({ interval_seconds: Math.max(60, Number(pollingState.interval_seconds) || 300) })}
              />
            </div>
            <div className="form-group">
              <label>单次上限</label>
              <input
                type="number"
                min={1}
                max={100}
                value={pollingState.limit || 20}
                disabled={pollingSaving || loading}
                onChange={(e) => setPollingState(prev => ({ ...prev, limit: e.target.value }))}
                onBlur={() => handlePollingConfigChange({ limit: Math.min(100, Math.max(1, Number(pollingState.limit) || 20)) })}
              />
            </div>
          </div>
          <div className="mail-control-meta">
            <span className={`badge ${pollingState.enabled ? 'badge-completed' : 'badge-ghost'}`}>{pollingState.enabled ? '后台轮询已开启' : '后台轮询已关闭'}</span>
            <span className={`badge ${pollingState.is_running ? 'badge-warning' : 'badge-ghost'}`}>{pollingState.is_running ? '正在执行' : '当前空闲'}</span>
            <span className="badge badge-ghost">最近成功 {pollingState.last_success_at ? formatDateTime(pollingState.last_success_at) : '未记录'}</span>
            {pollingSaving && <span className="badge badge-warning">正在保存配置</span>}
          </div>
          {!pollingSaving && pollingFeedback && (
            <div className={`mail-inline-alert ${pollingFeedback.tone === 'error' ? 'mail-inline-alert-error' : 'mail-inline-alert-success'}`}>
              {pollingFeedback.message}
              {pollingFeedback.savedAt ? ` · ${formatDateTime(pollingFeedback.savedAt)}` : ''}
            </div>
          )}
          {!!pollingState.last_error && (
            <div className="mail-inline-alert mail-inline-alert-error">{pollingState.last_error}</div>
          )}
          {pollingSummary && (
            <div className="mail-polling-summary">
              <div className="mail-polling-summary-grid">
                <div className="mail-polling-summary-card">
                  <div className="mail-polling-summary-label">扫描账户</div>
                  <div className="mail-polling-summary-value">{pollingSummary.account_count ?? 0}</div>
                </div>
                <div className="mail-polling-summary-card">
                  <div className="mail-polling-summary-label">成功</div>
                  <div className="mail-polling-summary-value">{pollingSummary.success_count ?? 0}</div>
                </div>
                <div className="mail-polling-summary-card">
                  <div className="mail-polling-summary-label">错误</div>
                  <div className="mail-polling-summary-value">{pollingSummary.error_count ?? 0}</div>
                </div>
                <div className="mail-polling-summary-card">
                  <div className="mail-polling-summary-label">新增来信</div>
                  <div className="mail-polling-summary-value">{pollingSummary.new_count ?? 0}</div>
                </div>
              </div>
              <details className="mail-detail-block">
                <summary>展开本轮轮询台账</summary>
                <div className="signal-list" style={{ marginTop: 'var(--space-sm)' }}>
                  {pollingResults.length === 0 ? (
                    <div className="signal-row">
                      <div>
                        <div className="signal-row-title">本轮没有明细</div>
                        <div className="signal-row-copy">可能当前没有开启可同步账户，或这一轮没有命中实际执行。</div>
                      </div>
                    </div>
                  ) : (
                    pollingResults.map((item, index) => (
                      <details key={`${item.account_id || 'result'}-${index}`} className="mail-detail-block mail-detail-block-card">
                        <summary>
                          <span>
                            {(accounts.find(account => account.account_id === item.account_id)?.display_name) || item.account_id || '未命名账户'}
                          </span>
                          <span className={`badge ${getExecutionBadgeClass(item.status)}`}>{getExecutionStatusLabel(item.status)}</span>
                        </summary>
                        <div className="signal-list" style={{ marginTop: 'var(--space-sm)' }}>
                          <div className="signal-row">
                            <div>
                              <div className="signal-row-title">本轮执行摘要</div>
                              <div className="signal-row-copy">{getPollingResultNarrative(item)}</div>
                            </div>
                          </div>
                          <div className="signal-row">
                            <div>
                              <div className="signal-row-title">轮询信箱</div>
                              <div className="signal-row-copy">{getInboxLabel(item.folder_kind || pollingState.folder_kind || 'inbox')}</div>
                            </div>
                            <span className="badge badge-ghost">{formatMailSyncCounts(item)}</span>
                          </div>
                          {!!item.sync?.finished_at && (
                            <div className="signal-row">
                              <div>
                                <div className="signal-row-title">最近完成</div>
                                <div className="signal-row-copy">{formatDateTime(item.sync.finished_at)}</div>
                              </div>
                              <span className="badge badge-ghost">{item.latest_uid || item.sync.latest_uid || '无 UID'}</span>
                            </div>
                          )}
                          {!!item.sync?.error_message && (
                            <div className="mail-inline-alert mail-inline-alert-error">
                              {item.sync.error_message}
                            </div>
                          )}
                        </div>
                      </details>
                    ))
                  )}
                </div>
              </details>
            </div>
          )}
        </article>

        <article className="mail-control-card">
          <div className="section-kicker">ACCOUNT CHECK</div>
          <div className="mail-control-title">当前账户链路</div>
          <div className="mail-control-copy">检定 SMTP 和 IMAP 是否真的打通，免得案头没有来信时，你分不清是世界安静还是线路已经断了。</div>
          {activeAccount ? (
            <>
              <div className="signal-list">
                <div className="signal-row">
                  <div>
                    <div className="signal-row-title">{activeAccount.display_name}</div>
                    <div className="signal-row-copy">{activeAccount.email_address}</div>
                  </div>
                  <span className="badge badge-pending">{getAutoMailPolicyLabel(activeAccount.auto_mail_policy)}</span>
                </div>
                <div className="signal-row">
                  <div>
                    <div className="signal-row-title">同步状态</div>
                    <div className="signal-row-copy">{activeAccount.sync_enabled ? '允许拉信' : '已暂停同步'}</div>
                  </div>
                  <span className={`badge ${activeAccount.sync_enabled ? 'badge-completed' : 'badge-ghost'}`}>{activeAccount.sync_enabled ? '同步开启' : '同步关闭'}</span>
                </div>
              </div>
              {accountTestResult?.results && (
                <div className="signal-list" style={{ marginTop: 'var(--space-sm)' }}>
                  {Object.entries(accountTestResult.results).map(([key, value]) => (
                    <div key={key} className="signal-row">
                      <div>
                        <div className="signal-row-title">{key.toUpperCase()}</div>
                        <div className="signal-row-copy">{value.message}</div>
                      </div>
                      <span className={`badge ${value.status === 'success' ? 'badge-completed' : value.status === 'error' ? 'badge-error' : 'badge-ghost'}`}>
                        {value.status === 'success' ? '通过' : value.status === 'error' ? '失败' : '跳过'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="mail-control-copy">先接入一个书信账户，这里才会显示真实链路状态。</div>
          )}
          <div className="inline-actions" style={{ marginTop: 'var(--space-md)' }}>
            <button className="btn btn-sm btn-ghost" onClick={requestOpenNotifyNetwork}>去接线页</button>
            <button className="btn btn-sm btn-ghost" onClick={handleAccountTest} disabled={!activeAccount || accountTesting || loading}>
              {accountTesting ? '检定中…' : '重新检定'}
            </button>
          </div>
        </article>

        <article className="mail-control-card">
          <div className="section-kicker">SYNC LEDGER</div>
          <div className="mail-control-title">最近同步台账</div>
          <div className="mail-control-copy">显示最近一轮拉信抓了多少、入了多少新信、最后停在什么 UID，而不是只剩一颗同步按钮。</div>
          <div className="signal-list">
            <div className="signal-row">
              <div>
                <div className="signal-row-title">最近状态</div>
                <div className="signal-row-copy">{syncStatus?.status || '尚未执行'}</div>
              </div>
              <span className={`badge ${syncStatus?.status === 'success' ? 'badge-completed' : syncStatus?.status === 'error' ? 'badge-error' : 'badge-ghost'}`}>
                {syncStatus?.status === 'success' ? '成功' : syncStatus?.status === 'error' ? '失败' : '未执行'}
              </span>
            </div>
            <div className="signal-row">
              <div>
                <div className="signal-row-title">抓取 / 新增</div>
                <div className="signal-row-copy">{syncStatus ? `${syncStatus.fetched_count || 0} / ${syncStatus.new_count || 0}` : '0 / 0'}</div>
              </div>
              <span className="badge badge-ghost">{syncStatus?.latest_uid || '无 UID'}</span>
            </div>
            <div className="signal-row">
              <div>
                <div className="signal-row-title">完成时间</div>
                <div className="signal-row-copy">{syncStatus?.finished_at ? formatDateTime(syncStatus.finished_at) : '尚未记录'}</div>
              </div>
            </div>
          </div>
          {syncStatus?.status === 'error' && (
            <div className="mail-inline-alert mail-inline-alert-error">
              最近一次拉信失败于 {formatDateTime(syncStatus.finished_at || syncStatus.started_at || syncStatus.created_at)}。
              {syncStatus.error_message ? ` ${syncStatus.error_message}` : ' 请先检查账户链路或立即重试同步。'}
            </div>
          )}
          {!!syncStatus?.error_message && (
            <div className="mail-inline-alert mail-inline-alert-error">{syncStatus.error_message}</div>
          )}
        </article>
      </div>
    </section>
  );
}
