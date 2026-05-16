import { memo, useMemo } from 'react';
import { renderMarkdownToHtml } from './markdown';

const AssistantMarkdown = memo(function AssistantMarkdown({ content, streaming = false }) {
  const rendered = useMemo(() => ({ __html: renderMarkdownToHtml(content) }), [content]);
  return (
    <div
      className={`markdown-body ${streaming ? 'is-streaming' : ''}`}
      dangerouslySetInnerHTML={rendered}
    />
  );
});

export default AssistantMarkdown;
