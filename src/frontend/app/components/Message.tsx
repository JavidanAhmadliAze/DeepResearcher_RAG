"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage } from "../types";
import SourceCard from "./SourceCard";

function BackgroundMessage({ message }: { message: ChatMessage }) {
  const lines = message.content.split("\n").filter((l) => l.trim());
  const header = lines[0] ?? "";
  const bullets = lines.slice(1).filter((l) => l.trim().startsWith("-"));

  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] rounded-lg px-3 py-2 bg-transparent border border-[#30363d] text-[#8b949e]">
        <div className="flex items-center gap-1.5 mb-1">
          <svg
            className="w-3 h-3 shrink-0 text-[#58a6ff]"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <span className="text-xs font-medium text-[#58a6ff]">
            Web research
          </span>
        </div>
        <p className="text-xs font-mono leading-snug text-[#8b949e]">
          {header}
        </p>
        {bullets.length > 0 && (
          <ul className="mt-1.5 space-y-0.5">
            {bullets.map((b, i) => (
              <li
                key={i}
                className="text-xs text-[#6e7681] pl-2 border-l border-[#30363d] truncate"
              >
                {b.replace(/^\s*-\s*/, "")}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function AiMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-xl p-4 bg-[#161b22] border border-[#30363d]">
        {message.statusLabel && (
          <p className="text-xs text-[#58a6ff] mb-3 font-medium">
            {message.statusLabel}
          </p>
        )}
        <div className="prose prose-invert prose-sm max-w-none
          prose-headings:text-[#e6edf3] prose-headings:font-semibold
          prose-h1:text-lg prose-h2:text-base prose-h3:text-sm
          prose-p:text-[#c9d1d9] prose-p:leading-relaxed
          prose-a:text-[#58a6ff] prose-a:no-underline hover:prose-a:underline
          prose-strong:text-[#e6edf3]
          prose-code:text-[#f0883e] prose-code:bg-[#21262d] prose-code:px-1 prose-code:rounded prose-code:text-xs
          prose-pre:bg-[#21262d] prose-pre:border prose-pre:border-[#30363d]
          prose-blockquote:border-l-[#58a6ff] prose-blockquote:text-[#8b949e]
          prose-li:text-[#c9d1d9]
          prose-hr:border-[#30363d]">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export default function Message({ message }: { message: ChatMessage }) {
  if (message.role === "background") {
    return <BackgroundMessage message={message} />;
  }

  if (message.role === "ai") {
    return <AiMessage message={message} />;
  }

  const isUser = message.role === "user";
  const isScope = message.role === "scope";

  const bubbleClass = isUser
    ? "bg-[#21262d] border border-[#30363d]"
    : isScope
    ? "bg-[rgba(88,166,255,0.08)] border border-[rgba(88,166,255,0.35)]"
    : "bg-[#161b22] border border-[#30363d]";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] rounded-xl p-4 ${bubbleClass}`}>
        {message.statusLabel && (
          <p className="text-xs text-[#58a6ff] mb-2 font-medium">
            {message.statusLabel}
          </p>
        )}
        {message.sources && message.sources.length > 0 ? (
          <div className="flex flex-col gap-2">
            {message.sources.map((source, i) => (
              <SourceCard key={i} source={source} />
            ))}
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {message.content}
          </p>
        )}
      </div>
    </div>
  );
}
