export default function AiChatConfigPanel({
  showConfig,
  setShowConfig,
  configForm,
  setConfigForm,
  saveConfig,
  testConnection,
  testing,
  clearChat,
  config,
}) {
  if (!showConfig) return null;

  return (
    <div className="card ai-config-panel ai-book-chapter ai-book-config-drawer">
      <div className="board-lane-header">
        <div>
          <div className="section-kicker">Control</div>
          <div className="board-lane-title">AI 配置台</div>
        </div>
        <button className="btn btn-sm btn-ghost" onClick={() => setShowConfig(false)}>关闭</button>
      </div>

      <div className="command-form">
        <div className="form-group">
          <label>API 地址</label>
          <input
            value={configForm.api_base}
            onChange={(event) => setConfigForm((form) => ({ ...form, api_base: event.target.value }))}
            placeholder="https://api.deepseek.com"
          />
        </div>
        <div className="form-group">
          <label>API Key</label>
          <input
            type="password"
            value={configForm.api_key}
            onChange={(event) => setConfigForm((form) => ({ ...form, api_key: event.target.value }))}
            placeholder="sk-..."
          />
        </div>
        <div className="form-group">
          <label>模型</label>
          <input
            value={configForm.model}
            onChange={(event) => setConfigForm((form) => ({ ...form, model: event.target.value }))}
            placeholder="deepseek-v4-pro"
          />
        </div>
        <div className="ai-inline-toolbar">
          <button className="btn btn-primary" onClick={saveConfig}>保存</button>
          <button className="btn" onClick={testConnection} disabled={testing}>
            {testing ? '测试中...' : '测试连接'}
          </button>
          <button className="btn btn-danger" onClick={clearChat}>清除对话</button>
        </div>
      </div>

      {config && (
        <div className="ai-config-meta">
          <div>当前模型: {config.model || '-'}</div>
          <div>API: {config.api_base || '-'}</div>
        </div>
      )}
    </div>
  );
}
