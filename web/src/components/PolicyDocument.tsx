import type { ReactNode } from "react";

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "paragraph"; text: string };

/**
 * Convierte el texto de la política (Markdown simple con líneas cortadas a
 * ancho fijo) en bloques: títulos, listas y párrafos. No interpreta HTML.
 */
export function parsePolicy(content: string): Block[] {
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let list: string[] | null = null;
  const flush = () => {
    if (paragraph.length) blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
    if (list) blocks.push({ kind: "list", items: list });
    paragraph = []; list = null;
  };
  for (const raw of content.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trim();
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (!line) { flush(); continue; }
    if (heading) { flush(); blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] }); continue; }
    const item = /^[-*]\s+(.*)$/.exec(line);
    if (item) {
      if (paragraph.length) { blocks.push({ kind: "paragraph", text: paragraph.join(" ") }); paragraph = []; }
      (list ??= []).push(item[1]);
      continue;
    }
    // Una línea que continúa un elemento de lista se une a ese elemento.
    if (list && !paragraph.length) { list[list.length - 1] += ` ${line}`; continue; }
    paragraph.push(line);
  }
  flush();
  return blocks;
}

/** Negritas **así** como <strong>; el resto se muestra como texto plano. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
}

export function PolicyDocument({ content, skipTitle = false }: { content: string; skipTitle?: boolean }) {
  const blocks = parsePolicy(content);
  const visible = skipTitle && blocks[0]?.kind === "heading" && blocks[0].level === 1 ? blocks.slice(1) : blocks;
  return <div className="policy-document">
    {visible.map((block, index) => {
      if (block.kind === "heading") return block.level <= 2
        ? <h3 key={index}>{inline(block.text)}</h3> : <h4 key={index}>{inline(block.text)}</h4>;
      if (block.kind === "list") return <ul key={index}>{block.items.map((item, i) => <li key={i}>{inline(item)}</li>)}</ul>;
      return <p key={index}>{inline(block.text)}</p>;
    })}
  </div>;
}
