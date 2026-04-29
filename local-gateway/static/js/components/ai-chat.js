/* local-gateway/static/js/components/ai-chat.js */
import { apiGet, apiPost, streamChat, toast } from '../api.js';
import { escapeHtml } from '../utils.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('aiChat', () => ({
    messages: [],
    input: '',
    conversationId: '',
    sending: false,

    // Config
    config: null,
    configLoading: true,
    showConfig: false,
    configForm: { api_base: '', api_key: '', model: '', temperature: 0.7, max_tokens: 2048 },

    // Panel state
    panelCollapsed: false,

    // Config error
    configError: null,

    async init() {
      this.$watch('$store.view.current', (val) => {
        if (val === 'ai-chat') this.onViewActive();
      });
      if (Alpine.store('view').current === 'ai-chat') await this.onViewActive();
    },

    async onViewActive() {
      await this.loadConfig();
    },

    async loadConfig() {
      this.configLoading = true;
      this.configError = null;
      try {
        const data = await apiGet('/api/chat/config');
        if (data.status === 'success') {
          this.config = data.config || data;
          this.configForm = {
            api_base: this.config.api_base || '',
            api_key: '',
            model: this.config.model || '',
            temperature: this.config.temperature ?? 0.7,
            max_tokens: this.config.max_tokens ?? 2048,
          };
        }
      } catch (e) {
        this.configError = '无法加载 AI 配置';
      } finally {
        this.configLoading = false;
      }
    },

    newConversation() {
      this.messages = [];
      this.conversationId = '';
      this.$nextTick(() => this.scrollToBottom());
    },

    async sendMessage() {
      const text = this.input.trim();
      if (!text || this.sending) return;
      this.input = '';

      // Add user message
      this.messages.push({ role: 'user', content: text });

      // Add AI placeholder
      const aiMsg = { role: 'assistant', content: '', toolCalls: [], streaming: true, showTools: true };
      this.messages.push(aiMsg);
      this.sending = true;
      this.scrollToBottom();

      try {
        await streamChat('/api/chat', {
          message: text,
          conversation_id: this.conversationId,
          stream: true,
        }, (event) => {
          if (event.type === 'token') {
            aiMsg.content += event.content;
            this.scrollToBottom();
          } else if (event.type === 'tool_call') {
            if (!aiMsg.toolCalls) aiMsg.toolCalls = [];
            aiMsg.toolCalls.push(event.function || event);
            this.scrollToBottom();
          } else if (event.type === 'done') {
            aiMsg.streaming = false;
            if (event.conversation_id) {
              this.conversationId = event.conversation_id;
            }
            this.scrollToBottom();
          } else if (event.type === 'error') {
            aiMsg.streaming = false;
            aiMsg.content = event.content || '请求出错';
            toast('AI 响应出错', 'error');
            this.scrollToBottom();
          }
        });
      } catch (e) {
        aiMsg.streaming = false;
        aiMsg.content = '请求失败，请检查网络连接';
        toast('发送消息失败', 'error');
      } finally {
        this.sending = false;
      }
    },

    handleKeydown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        this.sendMessage();
      }
    },

    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$el.querySelector('.chat-messages');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },

    async clearHistory() {
      if (!this.conversationId) {
        this.newConversation();
        return;
      }
      try {
        const data = await apiPost('/api/chat/clear', { conversation_id: this.conversationId });
        if (data.status === 'success') {
          toast('历史已清除', 'success');
        }
        this.newConversation();
      } catch (e) {
        toast('清除失败', 'error');
      }
    },

    async testConnection() {
      try {
        const data = await apiPost('/api/chat/test', {});
        if (data.status === 'success') {
          toast('连接测试成功', 'success');
        } else {
          toast(data.message || '连接测试失败', 'error');
        }
      } catch (e) {
        toast('连接测试失败', 'error');
      }
    },

    async saveConfig() {
      try {
        const body = { ...this.configForm };
        if (!body.api_key) delete body.api_key;
        const data = await apiPost('/api/chat/config', body);
        if (data.status === 'success') {
          toast('配置已保存', 'success');
          this.showConfig = false;
          await this.loadConfig();
        } else {
          toast(data.message || '保存失败', 'error');
        }
      } catch (e) {
        toast('保存配置失败', 'error');
      }
    },

    togglePanel() {
      this.panelCollapsed = !this.panelCollapsed;
    },

    toggleTools(msg) {
      if (msg.toolCalls && msg.toolCalls.length) {
        msg.showTools = !msg.showTools;
      }
    },

    escapeHtml: escapeHtml,
  }));
});
