import { useState } from 'react';
import { useApi, apiPost } from '../hooks/useApi';
import { useToast } from '../hooks/useToast';

const LANGUAGES = [
  { value: 'python', label: 'Python', icon: '🐍' },
  { value: 'javascript', label: 'JavaScript', icon: '📜' },
  { value: 'bash', label: 'Bash', icon: '🖥️' },
];

const PRESETS = {
  python: `import sys
print(f"Python {sys.version}")
print("Hello from sandbox!")

# Try your own code here
for i in range(5):
    print(f"  Count: {i}")`,

  javascript: `console.log("Node.js " + process.version);
console.log("Hello from sandbox!");

// Try your own code here
const fib = (n) => n <= 1 ? n : fib(n - 1) + fib(n - 2);
for (let i = 0; i < 8; i++) {
  console.log(\`  fib(\${i}) = \${fib(i)}\`);
}`,

  bash: `#!/bin/bash
echo "Hello from sandbox!"
echo "System: $(uname -s) $(uname -m)"
echo "Date: $(date)"

# Try your own code here
for i in 1 2 3; do
  echo "  Step $i"
done`,
};

export default function Sandbox() {
  const toast = useToast();
  const { loading, request } = useApi();

  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState(PRESETS.python);
  const [timeout, setTimeout_] = useState(30);
  const [output, setOutput] = useState(null);
  const [execTime, setExecTime] = useState(null);

  const handleLanguageChange = (lang) => {
    setLanguage(lang);
    setCode(PRESETS[lang] || '');
    setOutput(null);
  };

  const handleRun = async () => {
    if (!code.trim()) { toast('请输入代码', 'warning'); return; }
    setOutput(null);
    setExecTime(null);
    const startTime = performance.now();
    try {
      const data = await request(() => apiPost('/api/sandbox', {
        code,
        language,
        timeout,
      }));
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      setExecTime(elapsed);
      if (data.output !== undefined) {
        setOutput(data);
      } else if (data.result !== undefined) {
        setOutput(data.result);
      } else {
        setOutput(data);
      }
      toast(data.exit_code !== undefined && data.exit_code !== 0 ? '执行完成 (非零退出码)' : '执行成功', data.exit_code !== undefined && data.exit_code !== 0 ? 'warning' : 'success');
    } catch {
      toast('执行失败', 'error');
      setOutput({ error: true, stderr: '请求失败，请检查服务是否正常运行' });
    }
  };

  const handleReset = () => {
    setCode(PRESETS[language]);
    setOutput(null);
    setExecTime(null);
  };

  const renderOutput = () => {
    if (output === null) return null;

    const stdout = output.stdout || output.output || '';
    const stderr = output.stderr || output.error || '';
    const exitCode = output.exit_code ?? output.exitCode;
    const hasError = output.error || exitCode !== 0;

    return (
      <div style={{
        background: 'var(--bg-primary)',
        border: `1px solid ${hasError ? 'var(--error)' : 'var(--border)'}`,
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.85rem',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: 'var(--space-sm) var(--space-md)',
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-tertiary)',
        }}>
          <span style={{ fontWeight: 600, color: hasError ? 'var(--error)' : 'var(--success)' }}>
            {hasError ? '执行出错' : '执行完成'}
          </span>
          <div className="inline-actions">
            {exitCode !== undefined && <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>退出码: {exitCode}</span>}
            {execTime && <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>耗时: {execTime}s</span>}
          </div>
        </div>
        <div style={{ padding: 'var(--space-md)', maxHeight: 400, overflow: 'auto' }}>
          {stdout && <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)', margin: 0 }}>{stdout}</pre>}
          {stderr && <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--error)', margin: stdout ? 'var(--space-sm) 0 0 0' : 0 }}>{stderr}</pre>}
          {!stdout && !stderr && typeof output === 'object' && <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-primary)', margin: 0 }}>{JSON.stringify(output, null, 2)}</pre>}
          {!stdout && !stderr && typeof output === 'string' && <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-primary)', margin: 0 }}>{output}</pre>}
        </div>
      </div>
    );
  };

  return (
    <div className="page-shell">
      <section className="mission-masthead">
        <div className="mission-masthead-grid">
          <div>
            <span className="section-kicker">TEST RANGE</span>
            <h1 className="mission-title">沙盒页该像试验场，不该只是一个代码框加输出框。</h1>
            <div className="mission-copy">
              这里是快速验证代码片段、调小脚本和检查运行环境的地方。语言切换、超时和执行反馈都应该像一套试验装置。
            </div>
            <div className="mission-chip-row">
              <span className="badge badge-pending">当前语言 {LANGUAGES.find(item => item.value === language)?.label}</span>
              <span className="badge badge-warning">超时 {timeout} 秒</span>
              {execTime && <span className="badge badge-completed">最近执行 {execTime}s</span>}
            </div>
          </div>
          <div className="mission-sidecard">
            <div className="mission-sidecard-title">试验准则</div>
            <div className="mission-sidecard-copy">
              先选语言，再跑示例，再替换自己的片段。输出区不是附件，而是试验反馈面板。
            </div>
          </div>
        </div>
      </section>

      <div className="war-room-grid">
        <div className="war-room-stack">
          <section className="board-lane">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">LOADOUT</div>
                <h3 className="board-lane-title">试验配置</h3>
                <div className="board-lane-copy">语言切换和超时设定在同一个装配台里。</div>
              </div>
            </div>
            <div className="board-toolbar">
              <div style={{ display: 'flex', gap: 'var(--space-xs)', flexWrap: 'wrap' }}>
                {LANGUAGES.map(lang => (
                  <button
                    key={lang.value}
                    className={`btn ${language === lang.value ? 'btn-primary' : 'btn-ghost'}`}
                    onClick={() => handleLanguageChange(lang.value)}
                  >
                    {lang.icon} {lang.label}
                  </button>
                ))}
              </div>
              <div className="board-toolbar-spacer" />
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>超时(秒)</label>
                <input
                  type="number"
                  min={5}
                  max={300}
                  value={timeout}
                  onChange={e => setTimeout_(Math.max(5, Math.min(300, parseInt(e.target.value) || 30)))}
                  style={{ width: 84, textAlign: 'center' }}
                />
              </div>
            </div>
          </section>

          <section className="board-lane">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">EDITOR</div>
                <h3 className="board-lane-title">代码试验台</h3>
                <div className="board-lane-copy">保持现有后端执行逻辑，但让编辑器本身成为主要舞台。</div>
              </div>
              <button className="btn btn-sm btn-ghost" onClick={handleReset}>重置示例</button>
            </div>
            <textarea
              value={code}
              onChange={e => setCode(e.target.value)}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.85rem',
                lineHeight: 1.6,
                minHeight: 320,
                resize: 'vertical',
                tabSize: 4,
              }}
              placeholder="在此输入代码..."
              spellCheck={false}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
              <button className="btn btn-primary" onClick={handleRun} disabled={loading || !code.trim()}>
                {loading ? '执行中...' : '运行试验'}
              </button>
            </div>
          </section>
        </div>

        <div className="war-room-stack">
          <section className="board-lane">
            <div className="board-lane-header">
              <div>
                <div className="section-kicker">RESULT PANEL</div>
                <h3 className="board-lane-title">输出反馈</h3>
                <div className="board-lane-copy">这里显示运行结果、报错和执行耗时，像试验回报屏，而不是普通 console 区块。</div>
              </div>
            </div>
            {output !== null ? (
              renderOutput()
            ) : (
              <div className="empty-state" style={{ padding: 'var(--space-xl) 0' }}>
                <div className="empty-state-icon">🧪</div>
                <div className="empty-state-text">还没有试验结果</div>
                <div className="empty-state-hint">运行一段代码后，这里会显示输出与错误。</div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
