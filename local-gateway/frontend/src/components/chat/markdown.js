export function escapeHtml(value = '') {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function renderInlineMarkdown(text = '') {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return html;
}

export function highlightCode(code = '', language = '') {
  const escaped = escapeHtml(code);
  const lang = String(language || '').toLowerCase();

  if (lang === 'mermaid') return escaped;

  const patterns = [];
  if (['js', 'javascript', 'ts', 'typescript', 'python', 'py', 'bash', 'shell', 'json'].includes(lang)) {
    patterns.push(
      { regex: /\b(const|let|var|function|return|if|else|for|while|import|from|export|class|async|await|try|catch|def|lambda|yield|True|False|None|print|in|and|or|not|echo)\b/g, cls: 'token-keyword' },
      { regex: /\b(new|switch|case|break|continue|finally|raise|except|with|as|pass|global|nonlocal)\b/g, cls: 'token-keyword' },
      { regex: /(\".*?\"|\'.*?\'|\`.*?\`)/g, cls: 'token-string' },
      { regex: /\b(\d+(\.\d+)?)\b/g, cls: 'token-number' },
      { regex: /\b(true|false|null|undefined)\b/gi, cls: 'token-number' },
      { regex: /(\/\/.*$|#.*$)/gm, cls: 'token-comment' },
      { regex: /\b([A-Z][A-Za-z0-9_]+)\b/g, cls: 'token-type' },
    );
  }

  let html = escaped;
  patterns.forEach(({ regex, cls }) => {
    html = html.replace(regex, (match) => `<span class="${cls}">${match}</span>`);
  });
  return html;
}

export function renderMarkdownToHtml(markdown = '') {
  const normalized = String(markdown || '').replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const html = [];
  let inCodeBlock = false;
  let codeBuffer = [];
  let codeLanguage = '';
  let unorderedListBuffer = [];
  let orderedListBuffer = [];
  let blockquoteBuffer = [];
  let tableBuffer = [];

  const buildNestedListHtml = (items, type = 'ul') => {
    if (!items.length) return '';
    const root = [];
    const stack = [{ indent: -1, items: root }];

    items.forEach((item) => {
      const node = { ...item, children: [] };
      while (stack.length > 1 && item.indent <= stack[stack.length - 1].indent) stack.pop();
      stack[stack.length - 1].items.push(node);
      stack.push({ indent: item.indent, items: node.children });
    });

    const renderNodes = (nodes, listType) => {
      const tag = listType === 'ol' ? 'ol' : 'ul';
      return `<${tag}>${nodes.map(node => {
        const childType = (node.children[0]?.ordered ?? false) ? 'ol' : 'ul';
        return `<li>${renderInlineMarkdown(node.content)}${node.children.length ? renderNodes(node.children, childType) : ''}</li>`;
      }).join('')}</${tag}>`;
    };

    return renderNodes(root, type);
  };

  const flushUnorderedList = () => {
    if (!unorderedListBuffer.length) return;
    html.push(buildNestedListHtml(unorderedListBuffer.map(item => ({ ...item, ordered: false })), 'ul'));
    unorderedListBuffer = [];
  };

  const flushOrderedList = () => {
    if (!orderedListBuffer.length) return;
    html.push(buildNestedListHtml(orderedListBuffer.map(item => ({ ...item, ordered: true })), 'ol'));
    orderedListBuffer = [];
  };

  const flushBlockquote = () => {
    if (!blockquoteBuffer.length) return;
    html.push(`<blockquote>${blockquoteBuffer.map(item => renderInlineMarkdown(item)).join('<br/>')}</blockquote>`);
    blockquoteBuffer = [];
  };

  const flushTable = () => {
    if (tableBuffer.length < 2) {
      tableBuffer = [];
      return;
    }
    const [headerLine, separatorLine, ...bodyLines] = tableBuffer;
    if (!/\|/.test(separatorLine)) {
      tableBuffer = [];
      return;
    }
    const splitRow = (line) => line.split('|').map(cell => cell.trim()).filter((_, index, arr) => !(index === 0 && arr[0] === '') && !(index === arr.length - 1 && arr[arr.length - 1] === ''));
    const headers = splitRow(headerLine);
    const rows = bodyLines.map(splitRow);
    const tableHtml = `<table><thead><tr>${headers.map(cell => `<th>${renderInlineMarkdown(cell)}</th>`).join('')}</tr></thead><tbody>${
      rows.map(row => `<tr>${row.map(cell => `<td>${renderInlineMarkdown(cell)}</td>`).join('')}</tr>`).join('')
    }</tbody></table>`;
    html.push(`<div class="markdown-table-block"><button class="markdown-table-expand" data-table="${encodeURIComponent(tableHtml)}">展开表格</button>${tableHtml}</div>`);
    tableBuffer = [];
  };

  const flushCode = (isComplete = true) => {
    if (!codeBuffer.length) return;
    const rawCode = codeBuffer.join('\n');
    const code = highlightCode(rawCode, codeLanguage);
    const languageLabel = codeLanguage ? `<div class="markdown-code-lang">${escapeHtml(codeLanguage)}</div>` : '';
    const encoded = encodeURIComponent(rawCode);
    if (String(codeLanguage || '').toLowerCase() === 'mermaid') {
      const renderNote = isComplete
        ? 'Mermaid 图表源码已保留；若浏览器支持，将在上方自动渲染图形。'
        : 'Mermaid 代码块尚未输出完整；已先展示源码，闭合后再渲染图形。';
      html.push(`<div class="markdown-mermaid-block">${languageLabel}<button class="markdown-code-copy" data-code="${encoded}">复制</button><button class="markdown-code-expand" data-code="${encoded}" data-language="${escapeHtml(codeLanguage || 'mermaid')}">展开</button><div class="markdown-mermaid-render"></div><div class="markdown-mermaid-source" data-mermaid="${encoded}" data-mermaid-complete="${isComplete ? 'true' : 'false'}"><pre><code>${escapeHtml(rawCode)}</code></pre></div><div class="markdown-mermaid-note">${renderNote}</div></div>`);
    } else {
      html.push(`<div class="markdown-code-block">${languageLabel}<button class="markdown-code-copy" data-code="${encoded}">复制</button><button class="markdown-code-expand" data-code="${encoded}" data-language="${escapeHtml(codeLanguage || 'code')}">展开</button><pre><code>${code}</code></pre></div>`);
    }
    codeBuffer = [];
    codeLanguage = '';
  };

  lines.forEach((rawLine) => {
    const line = rawLine ?? '';

    if (line.trim().startsWith('```')) {
      flushUnorderedList();
      flushOrderedList();
      flushBlockquote();
      flushTable();
      if (inCodeBlock) {
        flushCode(true);
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
        codeLanguage = line.trim().slice(3).trim();
      }
      return;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      return;
    }

    if (!line.trim()) {
      flushUnorderedList();
      flushOrderedList();
      flushBlockquote();
      flushTable();
      html.push('');
      return;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushUnorderedList();
      flushOrderedList();
      flushBlockquote();
      flushTable();
      const level = headingMatch[1].length;
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      return;
    }

    const listMatch = line.match(/^(\s*)[-*+]\s+(.*)$/);
    if (listMatch) {
      flushBlockquote();
      flushOrderedList();
      flushTable();
      unorderedListBuffer.push({ indent: listMatch[1].length, content: listMatch[2] });
      return;
    }

    const orderedListMatch = line.match(/^(\s*)\d+\.\s+(.*)$/);
    if (orderedListMatch) {
      flushBlockquote();
      flushUnorderedList();
      flushTable();
      orderedListBuffer.push({ indent: orderedListMatch[1].length, content: orderedListMatch[2] });
      return;
    }

    const quoteMatch = line.match(/^\s*>\s?(.*)$/);
    if (quoteMatch) {
      flushUnorderedList();
      flushOrderedList();
      flushTable();
      blockquoteBuffer.push(quoteMatch[1]);
      return;
    }

    if (line.includes('|')) {
      flushUnorderedList();
      flushOrderedList();
      flushBlockquote();
      tableBuffer.push(line);
      return;
    }

    flushUnorderedList();
    flushOrderedList();
    flushBlockquote();
    flushTable();
    html.push(`<p>${renderInlineMarkdown(line)}</p>`);
  });

  flushUnorderedList();
  flushOrderedList();
  flushBlockquote();
  flushTable();
  flushCode(false);

  return html.filter(Boolean).join('');
}
