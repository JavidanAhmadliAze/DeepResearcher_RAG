"use client";

import { useState } from "react";
import type { AuthState } from "../types";

interface Props {
  apiBase: string;
  onAuth: (state: AuthState) => void;
}

export default function AuthModal({ apiBase, onAuth }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");

  function switchMode(next: "login" | "register") {
    setMode(next);
    setError("");
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "Unable to sign in.");
      }
      onAuth(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const res = await fetch(`${apiBase}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "Unable to create account.");
      }
      onAuth(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create account.");
    }
  }

  const inputClass =
    "w-full bg-[#0b1220] border border-[#30363d] rounded-xl px-4 py-3 text-sm text-[#c9d1d9] placeholder-[#8b949e] focus:outline-none focus:border-[#58a6ff]";

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="w-full max-w-md bg-[#111824] border border-[#30363d] rounded-2xl p-6 shadow-2xl">
        <h2 className="text-xl font-semibold mb-1">
          Sign in to Research Assistant
        </h2>
        <p className="text-sm text-[#8b949e] mb-5">
          Create an account or log in before starting a research run.
        </p>

        <div className="grid grid-cols-2 gap-2 mb-4">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              onClick={() => switchMode(m)}
              className={`py-2.5 rounded-xl text-sm font-medium capitalize transition-colors ${
                mode === m
                  ? "bg-[#58a6ff] text-white"
                  : "bg-[#1a2230] text-[#c9d1d9] hover:bg-[#222d40]"
              }`}
            >
              {m === "login" ? "Login" : "Register"}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-500/10 text-red-300 text-sm">
            {error}
          </div>
        )}

        {mode === "login" ? (
          <form onSubmit={handleLogin} className="flex flex-col gap-3">
            <input
              type="text"
              placeholder="Username or email"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className={inputClass}
              autoComplete="username"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              autoComplete="current-password"
              required
            />
            <button
              type="submit"
              className="w-full bg-[#58a6ff] text-white py-3 rounded-xl text-sm font-medium hover:bg-[#4d9de0] transition-colors"
            >
              Continue
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="flex flex-col gap-3">
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
              autoComplete="username"
              required
            />
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              autoComplete="email"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              autoComplete="new-password"
              required
            />
            <button
              type="submit"
              className="w-full bg-[#58a6ff] text-white py-3 rounded-xl text-sm font-medium hover:bg-[#4d9de0] transition-colors"
            >
              Create account
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
