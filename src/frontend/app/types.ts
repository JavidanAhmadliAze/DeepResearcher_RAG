export type AuthState = {
  token: string;
  user: { id: number; username: string };
};

export type TavilySource = {
  title: string;
  url: string;
  content: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "ai" | "scope" | "background";
  content: string;
  statusLabel?: string;
  sources?: TavilySource[];
};

export type Thread = {
  thread_id: string;
  title: string;
  created_at: string;
};
