"use client";

import type { ChatMessage } from "../types";
import SourceCard from "./SourceCard";

export default function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isScope = message.role === "scope";
  const isBackground = message.role === "background";

  const bubbleClass = isUser
    ? "bg-[#21262d] border border-[#30363d]"
    : isScope
    ? "bg-[rgba(88,166,255,0.08)] border border-[rgba(88,166,255,0.35)]"
    : isBackground
    ? "bg-[rgba(46,160,67,0.08)] border border-[rgba(46,160,67,0.30)]"
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
