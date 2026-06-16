const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AgentView = {
  role: string;
  status: string;
  current_task: string | null;
  queue_depth: number;
  model: string;
  metrics: { invocations: number; failures: number; avg_latency_s: number };
};

export type ChatResult = {
  plan_id: string;
  answer: string;
  tasks: { id: string; role: string; objective: string; status: string; result: string | null }[];
};

export type JarvisEvent = { kind: string; payload: Record<string, unknown>; ts: string };

export async function getAgents(): Promise<AgentView[]> {
  const r = await fetch(`${BASE}/agents`, { cache: "no-store" });
  if (!r.ok) throw new Error("agents unavailable");
  return r.json();
}

export async function sendChat(message: string): Promise<ChatResult> {
  const r = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok) throw new Error("chat failed");
  return r.json();
}

export function eventsUrl(): string {
  return `${BASE.replace(/^http/, "ws")}/ws/events`;
}
