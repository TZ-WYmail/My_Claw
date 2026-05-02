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
      if (data.exit_code !== undefined && data.exit_code !== 0) {
        toast('执行完成 (非零退出码)', 'warning');
      } else {
        toast('执行成功', 'success');
      }
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
            {hasError ? '✕ 执行出错' : '✓ 执行完成'}
          </span>
          {exitCode !== undefined && (
            <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              退出码: {exitCode}
            </span>
          )}
          {execTime && (
            <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
              耗时: {execTime}s
            </span>
          )}
        </div>
        <div style={{ padding: 'var(--space-md)', maxHeight: 400, overflow: 'auto' }}>
          {stdout && (
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)', margin: 0 }}>
              {stdout}
            </pre>
          )}
          {stderr && (
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--error)', margin: stdout ? 'var(--space-sm) 0 0 0' : 0 }}>
              {stderr}
            </pre>
          )}
          {!stdout && !stderr && typeof output === 'object' && (
            <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-primary)', margin: 0 }}>
              {JSON.stringify(output, null, 2)}
            </pre>
          )}
          {!stdout && !stderr && typeof output === 'string' && (
            <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-primary)', margin: 0 }}>
              {output}
            </pre>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: 'var(--space-lg)', maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 'var(--space-lg)' }}>沙盒执行</h2>

      {/* Language Selector & Controls */}
      <div className="card" style={{ marginBottom: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', marginLeft: 'auto' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>超时(秒)</label>
            <input
              type="number"
              min={5}
              max={300}
              value={timeout}
              onChange={e => setTimeout_(Math.max(5, Math.min(300, parseInt(e.target.value) || 30)))}
              style={{ width: 70, textAlign: 'center' }}
            />
          </div>
        </div>
      </div>

      {/* Editor + Output */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-md)' }}>
        {/* Code Editor */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-sm)' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              代码编辑器 — {LANGUAGES.find(l => l.value === language)?.label}
            </h3>
            <button className="btn btn-sm btn-ghost" onClick={handleReset}>重置示例</button>
          </div>
          <textarea
            value={code}
            onChange={e => setCode(e.target.value)}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.85rem',
              lineHeight: 1.6,
              minHeight: 240,
              resize: 'vertical',
              tabSize: 4,
            }}
            placeholder="在此输入代码..."
            spellCheck={false}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-sm)', marginTop: 'var(--space-md)' }}>
            <button className="btn btn-primary" onClick={handleRun} disabled={loading || !code.trim()}>
              {loading ? '执行中...' : '▶ 运行'}
            </button>
          </div>
        </div>

        {/* Output */}
        {output !== null && (
          <div>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>
              输出
            </h3>
            {renderOutput()}
          </div>
        )}
      </div>
    </div>
  );
}
