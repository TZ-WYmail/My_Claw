/* local-gateway/static/js/components/sandbox.js */
import { apiPost, toast } from '../api.js';
import { escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('sandbox', () => ({
    code: '# Write your code here\nprint("Hello, World!")',
    language: 'python',
    timeout: 30,

    executing: false,
    output: '',
    outputType: '', // '', 'success', 'error'
    executionTime: null,

    // Preset examples
    presets: {
      python: '# Write your code here\nprint("Hello, World!")',
      javascript: '// Write your code here\nconsole.log("Hello, World!");',
      bash: '# Write your code here\necho "Hello, World!"',
    },

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'sandbox') this.onViewActive();
      });
      if (Alpine.store('view').current === 'sandbox') await this.onViewActive();
    },

    onViewActive() {
      // Nothing special needed on view activation
    },

    loadPreset(lang) {
      this.language = lang;
      this.code = this.presets[lang] || '';
      this.clearOutput();
    },

    async execute() {
      if (!this.code.trim()) {
        toast('请输入代码', 'error');
        return;
      }
      this.executing = true;
      this.output = '';
      this.outputType = '';
      this.executionTime = null;

      const startTime = performance.now();

      try {
        const data = await apiPost('/api/sandbox', {
          code: this.code,
          language: this.language,
          timeout: this.timeout,
        });
        this.executionTime = ((performance.now() - startTime) / 1000).toFixed(2);

        if (data.status === 'success' || data.status === 'ok') {
          this.output = data.output || data.stdout || '(无输出)';
          this.outputType = 'success';
          if (data.stderr) {
            this.output += '\n\n--- stderr ---\n' + data.stderr;
          }
        } else if (data.error || data.stderr) {
          this.output = data.error || data.stderr || '执行出错';
          this.outputType = 'error';
        } else if (data.status === 'error' || data.status === 'failed') {
          this.output = data.message || data.output || '执行出错';
          this.outputType = 'error';
        } else {
          this.output = data.output || data.stdout || JSON.stringify(data, null, 2);
          this.outputType = 'success';
        }
      } catch (e) {
        this.output = e.message || '请求失败，请检查连接';
        this.outputType = 'error';
        this.executionTime = ((performance.now() - startTime) / 1000).toFixed(2);
        toast('执行请求失败', 'error');
      } finally {
        this.executing = false;
      }
    },

    clearOutput() {
      this.output = '';
      this.outputType = '';
      this.executionTime = null;
    },

    escapeHtml: escapeHtml,
  }));
});
