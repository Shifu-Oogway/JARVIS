"use client";

import { useEffect, useRef, useState } from "react";
import {
  getAgents, sendChat, eventsUrl,
  type AgentView, type JarvisEvent, type ChatResult,
} from "@/lib/api";

export default function CommandCenter() {
  const [agents, setAgents] = useState<AgentView[]>([]);
  const [events, setEvents] = useState<JarvisEvent[]>([]);
  const [online, setOnline] = useState(false);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<ChatResult | null>(null);
  const [busy, setBusy] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  // poll agents
  useEffect(() => {
    let alive = true;
    const tick = () =>
      getAgents().then((a) => alive && (setAgents(a), setOnline(true)))
        .catch(() => alive && setOnline(false));
    tick();
    const id = setInterval(tick, 4000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  // live event feed over websocket
  useEffect(() => {
    const ws = new WebSocket(eventsUrl());
    ws.onmessage = (m) =>
      setEvents((prev) => [JSON.parse(m.data) as JarvisEvent, ...prev].slice(0, 60));
    return () => ws.close();
  }, []);

  async function submit() {
    if (!input.trim() || busy) return;
    setBusy(true);
    try { setResult(await sendChat(input)); }
    catch { setResult(null); }
    finally { setBusy(false); }
  }

  return (
    <main className="mx-auto max-w-[1400px] px-5 py-6">
      <header className="mb-6 flex items-center justify-between">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-lg font-bold tracking-[0.32em] text-text">JARVIS</span>
          <span className="eyebrow">Enterprise AI Operating System</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={online ? "live-dot" : "live-dot status-offline"} />
          <span className="eyebrow">{online ? "Core online" : "Core unreachable"}</span>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Command Console */}
        <section className="panel lg:col-span-2">
          <div className="panel-head"><span className="eyebrow">Command Console</span></div>
          <div className="p-4">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="Issue a directive — Jarvis Core will decompose and dispatch it…"
                className="w-full rounded-md border border-edge bg-ink px-3 py-2 text-sm text-text outline-none placeholder:text-muted focus:border-live"
              />
              <button
                onClick={submit} disabled={busy}
                className="rounded-md border border-edge px-4 py-2 font-mono text-xs uppercase tracking-widest text-live hover:border-live disabled:opacity-40"
              >
                {busy ? "Routing" : "Execute"}
              </button>
            </div>

            {result && (
              <div className="mt-4 space-y-3">
                <div className="rounded-md border border-edge bg-ink/60 p-3">
                  <div className="eyebrow mb-2">Synthesis</div>
                  <p className="whitespace-pre-wrap text-sm text-text">{result.answer}</p>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {result.tasks.map((t) => (
                    <div key={t.id} className="rounded-md border border-edge p-2">
                      <div className="flex justify-between">
                        <span className="font-mono text-[11px] uppercase tracking-wider text-surge">{t.role}</span>
                        <span className={`font-mono text-[11px] status-${t.status === "succeeded" ? "busy" : t.status === "failed" ? "error" : "idle"}`}>{t.status}</span>
                      </div>
                      <p className="mt-1 text-xs text-muted">{t.objective}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Event Feed */}
        <section className="panel">
          <div className="panel-head">
            <span className="eyebrow">Event Feed</span>
            <span className="font-mono text-[11px] text-muted">{events.length}</span>
          </div>
          <div ref={feedRef} className="max-h-[420px] overflow-auto p-3 font-mono text-[11px]">
            {events.length === 0 && <p className="text-muted">Awaiting telemetry…</p>}
            {events.map((e, i) => (
              <div key={i} className="flex gap-2 border-b border-edge/40 py-1">
                <span className="text-muted">{e.ts.slice(11, 19)}</span>
                <span className="text-live">{e.kind}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Agent Control Center */}
        <section className="panel lg:col-span-3">
          <div className="panel-head"><span className="eyebrow">Agent Control Center</span></div>
          <div className="grid grid-cols-2 gap-px bg-edge/40 sm:grid-cols-4 lg:grid-cols-8">
            {agents.map((a) => (
              <div key={a.role} className="bg-panel p-3">
                <div className="flex items-center gap-1.5">
                  <span className={`live-dot status-${a.status}`} />
                  <span className="font-mono text-[11px] uppercase tracking-wider text-text">{a.role}</span>
                </div>
                <p className="mt-2 truncate text-[10px] text-muted" title={a.model}>{a.model}</p>
                <p className="mt-1 font-mono text-[10px] text-muted">
                  inv {a.metrics.invocations} · fail {a.metrics.failures}
                </p>
              </div>
            ))}
            {agents.length === 0 && <p className="bg-panel p-3 text-xs text-muted">No agents reporting.</p>}
          </div>
        </section>

        {/* Placeholder centers (Phase 2 subsystems) */}
        {[
          ["Workflow Center", "DAG execution graphs land in Phase 2."],
          ["Memory Center", "Rolling context + Obsidian vault land in Phase 2."],
          ["Maintenance Center", "Backups, updates & health land in Phase 2."],
        ].map(([title, note]) => (
          <section key={title} className="panel">
            <div className="panel-head"><span className="eyebrow">{title}</span></div>
            <div className="p-4 text-xs text-muted">{note}</div>
          </section>
        ))}
      </div>
    </main>
  );
}
