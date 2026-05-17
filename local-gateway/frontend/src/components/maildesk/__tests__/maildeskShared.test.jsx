import { render, screen } from '@testing-library/react';
import {
  buildMailtoReplyLink,
  normalizePlainLink,
  renderPlainTextWithLinks,
  sanitizeMailHref,
  sanitizeMailHtml,
} from '../maildeskShared.jsx';

describe('maildeskShared', () => {
  it('sanitizes hrefs and blocks unsafe protocols', () => {
    expect(sanitizeMailHref('https://example.com/path')).toBe('https://example.com/path');
    expect(sanitizeMailHref('mailto:user@example.com')).toBe('mailto:user@example.com');
    expect(sanitizeMailHref('javascript:alert(1)')).toBe('');
    expect(sanitizeMailHref('data:text/html,hi')).toBe('');
  });

  it('sanitizes html while keeping safe anchors', () => {
    const html = sanitizeMailHtml('<div><script>alert(1)</script><a href="https://example.com">Go</a><img src=x />tail</div>');

    expect(html).toContain('href="https://example.com/"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('tail');
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<img');
  });

  it('renders plain text urls and emails as links', () => {
    render(<div>{renderPlainTextWithLinks('Check https://example.com/test and alex@example.com now.')}</div>);

    expect(screen.getByRole('link', { name: 'https://example.com/test' })).toHaveAttribute('href', 'https://example.com/test');
    expect(screen.getByRole('link', { name: 'alex@example.com' })).toHaveAttribute('href', 'mailto:alex@example.com');
  });

  it('normalizes plain links with trailing punctuation', () => {
    expect(normalizePlainLink('www.example.com,')).toEqual({
      href: 'https://www.example.com',
      label: 'www.example.com',
      suffix: ',',
    });
  });

  it('builds mailto reply link from inbound message fallback', () => {
    const href = buildMailtoReplyLink(
      { subject: 'Schedule update' },
      {
        messages: [
          {
            direction: 'inbound',
            from_email: 'alex@example.com',
            reply_to: [],
          },
        ],
      },
      null,
    );

    expect(href).toBe('mailto:alex@example.com?subject=Re%3A+Schedule+update');
  });
});
