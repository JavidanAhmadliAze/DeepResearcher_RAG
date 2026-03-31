"use client";

import type { Thread } from "../types";

interface Props {
  threads: Thread[];
  currentThreadId: string;
  username?: string;
  onNewChat: () => void;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  onLogout: () => void;
}

export default function Sidebar({
  threads,
  currentThreadId,
  username,
  onNewChat,
  onSelectThread,
  onDeleteThread,
  onLogout,
}: Props) {
  return (
    <aside className="w-64 shrink-0 bg-[#161b22] border-r border-[#30363d] flex-col hidden md:flex">
      <div className="p-4 border-b border-[#30363d]">
        <h1 className="text-base font-semibold text-[#58a6ff] mb-3">
          Research Assistant
        </h1>
        <button
          onClick={onNewChat}
          className="w-full py-2 text-sm text-[#c9d1d9] border border-[#30363d] rounded-md hover:bg-[#1f242c] transition-colors"
        >
          + New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {threads.map((thread) => (
          <div
            key={thread.thread_id}
            className={`group flex items-center gap-1 rounded-md mb-0.5 pr-1 ${
              thread.thread_id === currentThreadId
                ? "bg-[#21262d]"
                : "hover:bg-[#1f242c]"
            }`}
          >
            <button
              onClick={() => onSelectThread(thread.thread_id)}
              className={`flex-1 text-left px-3 py-2 text-sm truncate transition-colors ${
                thread.thread_id === currentThreadId
                  ? "text-[#c9d1d9]"
                  : "text-[#8b949e] group-hover:text-[#c9d1d9]"
              }`}
            >
              {thread.title}
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteThread(thread.thread_id);
              }}
              title="Delete chat"
              className="shrink-0 opacity-0 group-hover:opacity-100 p-1 rounded text-[#8b949e] hover:text-red-400 hover:bg-red-500/10 transition-all"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path
                  d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {username && (
        <div className="p-4 border-t border-[#30363d] flex flex-col gap-2">
          <span className="text-xs text-[#8b949e]">Signed in as {username}</span>
          <button
            onClick={onLogout}
            className="w-full py-2 text-sm text-[#c9d1d9] bg-[#273244] rounded-md hover:bg-[#334055] transition-colors"
          >
            Log out
          </button>
        </div>
      )}
    </aside>
  );
}
