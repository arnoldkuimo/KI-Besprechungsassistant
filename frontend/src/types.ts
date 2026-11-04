export type Account = { id: number; name: string; role: string };
export type Segment = {
  id: number;
  speaker: string | null;
  timestamp: string | null;
  text: string;
};
export type Entry = {
  id?: string;
  text: string;
  quote: string;
  source_ids: number[];
  owner?: string | null;
  due_text?: string | null;
  due_date?: string | null;
};
export const sections = ["summary", "decisions", "tasks", "open_questions"] as const;
export type Section = (typeof sections)[number];
export type Report = Record<Section, Entry[]> & {
  warnings?: string[];
  manual_edit?: boolean;
};
export type Meeting = {
  id: number;
  title: string;
  meeting_date: string;
  participants: string[];
  status: string;
  current_revision: number;
  source_version: number;
  owner_id: number;
  reviewer_id: number;
  owner_name: string;
  reviewer_name: string;
  last_error: string | null;
};
export type Detail = {
  meeting: Meeting;
  report: Report | null;
  editable_report: Report | null;
  revision: number;
  approved: boolean;
  approved_by: string | null;
  approved_at: string | null;
  source: { version: number; segments: Segment[] };
  current_source: { version: number; segments: Segment[] };
  versions: { number: number; approved: boolean }[];
  task_states: Record<string, string>;
  events: {
    id: number;
    description: string;
    actor: string;
    created_at: string;
  }[];
  processing: { stage: string; state: string; mode: string } | null;
};
export type Meta = {
  provider: string;
  workflow_mode: string;
  configured: boolean;
};

export const labels: Record<Section, string> = {
  summary: "Zusammenfassung",
  decisions: "Entscheidungen",
  tasks: "Aufgaben",
  open_questions: "Offene Fragen",
};
export const statuses: Record<string, string> = {
  queued: "Vorgemerkt",
  processing: "In Verarbeitung",
  draft: "Entwurf",
  review: "Zur Prüfung",
  approved: "Freigegeben",
  changes_requested: "Änderungen erbeten",
  error: "Unterbrochen",
};

export async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => ({}));
    throw new Error(
      typeof problem.detail === "string"
        ? problem.detail
        : `Anfrage fehlgeschlagen (${response.status}). Eingaben prüfen.`,
    );
  }
  return response.json();
}

export function sourceText(segments: Segment[]) {
  return segments
    .map((s) => `${s.timestamp ? `[${s.timestamp}] ` : ""}${s.speaker ? `${s.speaker}: ` : ""}${s.text}`)
    .join("\n");
}
