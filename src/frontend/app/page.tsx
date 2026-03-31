"use client";

import { useState, useEffect, useRef } from "react";
import AuthModal from "./components/AuthModal";
import Sidebar from "./components/Sidebar";
import Message from "./components/Message";
import MessageInput from "./components/MessageInput";
import type { AuthState, ChatMessage, Thread, TavilySource } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const AUTH_KEY = "deep-research-auth";

function parseTavilySources(content: string): TavilySource[] | null {
  try {
    const parsed = JSON.parse(content);
    if (Array.isArray(parsed?.results)) {
      return parsed.results.map((r: Record<string, string>) => ({
        title: r.title ?? "Untitled",
        url: r.url ?? "",
        content: r.content ?? r.snippet ?? "",
      }));
    }
  } catch {
    // not JSON or not Tavily format
  }
  return null;
}

export default function Home() {
  const [auth, setAuth] = useState<AuthState | null>(null);
  const [threadId, setThreadId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [threadStatus, setThreadStatus] = useState("Ready");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Restore auth from localStorage on mount
  useEffect(() => {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return;
    try {
      const state = JSON.parse(raw) as AuthState;
      verifySession(state);
    } catch {
      localStorage.removeItem(AUTH_KEY);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Assign a new unique thread ID on mount
  useEffect(() => {
    setThreadId(crypto.randomUUID());
  }, []);

  // Load thread list whenever auth changes
  useEffect(() => {
    if (auth) loadThreads(auth.token);
  }, [auth]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function verifySession(state: AuthState) {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${state.token}` },
      });
      if (!res.ok) throw new Error("session expired");
      const data = await res.json();
      persistAuth({ token: state.token, user: data.user });
    } catch {
      clearAuth();
    }
  }

  async function loadThreads(token: string) {
    try {
      const res = await fetch(`${API_BASE}/threads`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      setThreads(await res.json());
    } catch {
      // silently ignore — sidebar just stays empty
    }
  }

  function persistAuth(state: AuthState | null) {
    setAuth(state);
    if (state) {
      localStorage.setItem(AUTH_KEY, JSON.stringify(state));
    } else {
      localStorage.removeItem(AUTH_KEY);
    }
  }

  function clearAuth() {
    persistAuth(null);
    setThreadStatus("Sign in required");
  }

  function newChat() {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setThreadId(crypto.randomUUID());
    setMessages([]);
    setThreadStatus("Ready");
  }

  async function deleteThread(tid: string) {
    if (!auth) return;
    try {
      const res = await fetch(`${API_BASE}/threads/${tid}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${auth.token}` },
      });
      if (!res.ok && res.status !== 404) throw new Error();
      setThreads((prev) => prev.filter((t) => t.thread_id !== tid));
      if (tid === threadId) newChat();
    } catch {
      // silently ignore
    }
  }

  async function selectThread(tid: string) {
    if (!auth) return;
    setThreadId(tid);
    setMessages([]);
    setThreadStatus("Loading...");
    try {
      const res = await fetch(`${API_BASE}/history/${tid}`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      });
      if (!res.ok) throw new Error();
      const history: { role: string; content: string }[] = await res.json();
      setMessages(
        history.map((m) => ({
          id: crypto.randomUUID(),
          role: m.role === "assistant" ? "ai" : "user",
          content: m.content,
        }))
      );
      setThreadStatus("Ready");
    } catch {
      setThreadStatus("Error loading history");
    }
  }

  async function sendMessage(text: string) {
    if (!auth || !text.trim() || isStreaming) return;

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text },
    ]);
    setIsStreaming(true);
    setThreadStatus("Researching...");

    let aiMsgId: string | null = null;

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${auth.token}`,
        },
        body: JSON.stringify({ message: text, thread_id: threadId }),
        signal: abortRef.current.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Request failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          aiMsgId = handleEvent(block, aiMsgId);
        }
      }
      if (buffer.trim()) aiMsgId = handleEvent(buffer, aiMsgId);

      // Refresh sidebar thread list
      loadThreads(auth.token);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      const msg = err instanceof Error ? err.message : "An error occurred.";
      if (aiMsgId) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? { ...m, content: msg, statusLabel: undefined }
              : m
          )
        );
      } else {
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "ai", content: msg },
        ]);
      }
      setThreadStatus("Error");
    } finally {
      setIsStreaming(false);
    }
  }

  function handleEvent(raw: string, aiMsgId: string | null): string | null {
    let eventType = "message";
    let data = "";

    for (const line of raw.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) data += line.slice(5).trimStart();
    }

    if (!data) return aiMsgId;

    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(data);
    } catch {
      return aiMsgId;
    }

    switch (eventType) {
      case "status": {
        setThreadStatus((payload.message as string) ?? "Researching...");
        break;
      }

      case "scope_message": {
        const label =
          payload.node === "write_research_brief"
            ? "Research brief"
            : "Scope agent";
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "scope",
            content: (payload.content as string) ?? "",
            statusLabel: label,
          },
        ]);
        break;
      }

      case "background_message": {
        const content = (payload.content as string) ?? "";
        const sources = parseTavilySources(content);
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "background",
            content: sources ? "" : content,
            statusLabel: "Web research",
            sources: sources ?? undefined,
          },
        ]);
        break;
      }

      case "content": {
        const delta = (payload.delta as string) ?? "";
        if (!aiMsgId) {
          const newId = crypto.randomUUID();
          setMessages((prev) => [
            ...prev,
            {
              id: newId,
              role: "ai",
              content: delta,
              statusLabel: "Writing final response",
            },
          ]);
          return newId;
        }
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId ? { ...m, content: m.content + delta } : m
          )
        );
        break;
      }

      case "done": {
        if (aiMsgId) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId ? { ...m, statusLabel: undefined } : m
            )
          );
        }
        setThreadStatus(
          payload.awaiting_clarification ? "Waiting for your answer" : "Ready"
        );
        break;
      }

      case "error": {
        const errMsg =
          (payload.message as string) ?? "The assistant could not finish.";
        if (aiMsgId) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: errMsg, statusLabel: undefined }
                : m
            )
          );
        } else {
          setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: "ai", content: errMsg },
          ]);
        }
        setThreadStatus("Error");
        break;
      }
    }

    return aiMsgId;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {!auth && <AuthModal apiBase={API_BASE} onAuth={persistAuth} />}

      <Sidebar
        threads={threads}
        currentThreadId={threadId}
        username={auth?.user.username}
        onNewChat={newChat}
        onSelectThread={selectThread}
        onDeleteThread={deleteThread}
        onLogout={clearAuth}
      />

      <main className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="h-[60px] border-b border-[#30363d] flex items-center px-6 shrink-0">
          <div className="flex flex-col gap-0.5">
            <span className="font-medium text-sm">Deep Research Assistant</span>
            <span className="text-xs text-[#8b949e]">{threadStatus}</span>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-[10%] py-8 flex flex-col gap-4">
          {messages.map((msg) => (
            <Message key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <MessageInput
          onSend={sendMessage}
          disabled={!auth || isStreaming}
        />
      </main>
    </div>
  );
}
