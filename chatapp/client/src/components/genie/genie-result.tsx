import { useState } from 'react';
import { ChevronRightIcon } from 'lucide-react';

interface GenieResultProps {
  sql?: string;
  columns?: { name: string }[];
  rows?: any[][];
  narrative?: string;
}

/** Simple markdown: **bold**, *italic*, `code`, and line breaks */
function renderMarkdown(text: string) {
  // Split into segments, preserving markdown tokens
  const parts: (string | JSX.Element)[] = [];
  let remaining = text;
  let key = 0;

  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\n)/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(remaining)) !== null) {
    // Text before match
    if (match.index > lastIndex) {
      parts.push(remaining.slice(lastIndex, match.index));
    }

    if (match[2]) {
      // **bold**
      parts.push(<strong key={key++} className="font-semibold">{match[2]}</strong>);
    } else if (match[3]) {
      // *italic*
      parts.push(<em key={key++}>{match[3]}</em>);
    } else if (match[4]) {
      // `code`
      parts.push(
        <code key={key++} className="rounded bg-muted px-1 py-0.5 text-xs font-mono">
          {match[4]}
        </code>,
      );
    } else if (match[0] === '\n') {
      parts.push(<br key={key++} />);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < remaining.length) {
    parts.push(remaining.slice(lastIndex));
  }

  return parts;
}

export function GenieResult({ sql, columns, rows, narrative }: GenieResultProps) {
  const [sqlOpen, setSqlOpen] = useState(false);

  return (
    <div className="space-y-3">
      {narrative && (
        <div className="text-sm text-foreground leading-relaxed">
          {renderMarkdown(narrative)}
        </div>
      )}

      {columns && rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b bg-muted/30">
                {columns.map((col, i) => (
                  <th key={i} className="px-3 py-2 text-left font-medium">
                    {col.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b last:border-0">
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-2">
                      {cell != null ? String(cell) : '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {columns && rows && rows.length === 0 && (
        <p className="text-xs text-muted-foreground italic">No results returned.</p>
      )}

      {sql && (
        <div className="rounded-lg border">
          <button
            onClick={() => setSqlOpen(!sqlOpen)}
            className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left hover:bg-muted/30 transition-colors"
          >
            <ChevronRightIcon
              className={`h-3 w-3 text-muted-foreground transition-transform ${sqlOpen ? 'rotate-90' : ''}`}
            />
            <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
              Generated SQL
            </span>
          </button>
          {sqlOpen && (
            <pre className="overflow-x-auto border-t p-3 text-xs font-mono text-muted-foreground">
              {sql}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
