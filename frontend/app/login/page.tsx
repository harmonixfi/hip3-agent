"use client";

import { useState, useTransition } from "react";
import { login, type LoginState } from "./actions";

export default function LoginPage() {
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleSubmit(formData: FormData) {
    setError("");
    startTransition(async () => {
      try {
        const result: LoginState = await login(formData);
        if (result.error) {
          setError(result.error);
        }
      } catch {
        // Successful login calls redirect(), which throws — navigation handles it
      }
    });
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="card space-y-6">
          <div>
            <h1 className="text-xl font-bold text-white">OpenClaw Dashboard</h1>
            <p className="text-sm text-gray-400 mt-1">Enter password to continue</p>
          </div>

          <form action={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className="sr-only">Password</label>
              <input
                id="password"
                type="password"
                name="password"
                placeholder="Password"
                required
                autoFocus
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
              />
            </div>

            {error && (
              <p role="alert" className="text-red-400 text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={isPending}
              className="w-full bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium py-2 px-4 rounded transition-colors"
            >
              {isPending ? "Checking..." : "Enter"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
