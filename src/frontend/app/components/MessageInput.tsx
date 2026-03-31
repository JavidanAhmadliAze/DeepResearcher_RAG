"use client";

import { useState, useRef } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function MessageInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setText(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = `${ta.scrollHeight}px`;
    }
  }

  return (
    <footer className="px-[10%] pb-10 pt-4 shrink-0">
      <div className="flex items-end gap-2 bg-[#161b22] border border-[#30363d] rounded-xl px-4 py-2.5 shadow-lg">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Type your research query..."
          rows={1}
          className="flex-1 bg-transparent text-sm text-[#c9d1d9] placeholder-[#8b949e] resize-none outline-none max-h-48 py-1"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="bg-[#58a6ff] text-white rounded-lg p-2 disabled:opacity-30 disabled:cursor-default hover:bg-[#4d9de0] transition-colors shrink-0"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M22 2L11 13"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M22 2L15 22L11 13L2 9L22 2Z"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
    </footer>
  );
}
