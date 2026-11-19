/**
 * Minimal, dependency-free markdown for Genie and agent answers:
 * paragraphs, #/##/### headings, - / * / 1. lists, **bold**, *italic*, `code`.
 * Text is rendered as React nodes (never innerHTML), so model output can't inject markup.
 */
import type { ReactNode } from "react";

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;

function inline(text: string, keyBase: string): ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    const key = `${keyBase}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={key}>{part.slice(1, -1)}</code>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>;
    return part;
  });
}

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "h"; level: number; text: string }
  | { kind: "list"; ordered: boolean; items: string[] };

function parse(src: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] | null = null;
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (para) blocks.push({ kind: "p", lines: para });
    if (list) blocks.push({ kind: "list", ...list });
    para = null;
    list = null;
  };
  for (const raw of src.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    const ul = /^\s*[-*•]\s+(.*)$/.exec(line);
    const ol = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flush();
    } else if (h) {
      flush();
      blocks.push({ kind: "h", level: h[1].length, text: h[2] });
    } else if (ul || ol) {
      const ordered = !ul;
      const item = (ul ?? ol)![1];
      if (!list || list.ordered !== ordered) {
        flush();
        list = { ordered, items: [] };
      }
      list.items.push(item);
    } else {
      if (!para) {
        flush();
        para = [];
      }
      para.push(line.trim());
    }
  }
  flush();
  return blocks;
}

export default function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      {parse(text).map((b, i) => {
        const k = String(i);
        if (b.kind === "h") return <div className={`md-h h${b.level}`} key={k}>{inline(b.text, k)}</div>;
        if (b.kind === "list") {
          const List = b.ordered ? "ol" : "ul";
          return (
            <List key={k}>
              {b.items.map((it, j) => <li key={j}>{inline(it, `${k}-${j}`)}</li>)}
            </List>
          );
        }
        return <p key={k}>{inline(b.lines.join(" "), k)}</p>;
      })}
    </div>
  );
}
