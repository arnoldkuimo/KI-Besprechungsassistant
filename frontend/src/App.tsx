import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCheck,
  ChevronRight,
  ClipboardList,
  Download,
  FileText,
  History,
  ListChecks,
  LoaderCircle,
  MessageSquare,
  Pencil,
  Plus,
  Quote,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { createRoot } from "react-dom/client";
import {
  type Account,
  type Detail,
  type Entry,
  type Meta,
  type Meeting,
  type Report,
  type Section,
  labels,
  request,
  sections,
  sourceText,
  statuses,
} from "./types";
import { example } from "./example";
import "./style.css";

function Modal({
  title,
  close,
  children,
  wide = false,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      if (e.key === "Tab") {
        const controls = dialog.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled):not([type="file"]), select:not(:disabled), textarea:not(:disabled), a[href]',
        );
        if (!controls?.length) return;
        const first = controls[0],
          last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handler);
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = old;
    };
  }, []);
  return (
    <div
      className="overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        ref={dialog}
        className={`dialog ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon" onClick={close} title="Schließen" aria-label="Schließen" autoFocus>
            <X size={19} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

function NewMeeting({
  meta,
  accounts,
  close,
  created,
}: {
  meta: Meta;
  accounts: Account[];
  close: () => void;
  created: (id: number) => void;
}) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(new Date().toLocaleDateString("en-CA"));
  const [participants, setParticipants] = useState("");
  const [reviewer, setReviewer] = useState(2);
  const [text, setText] = useState("");
  const [audio, setAudio] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = {
      title,
      meeting_date: date,
      participants: participants
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean),
      reviewer_id: reviewer,
      transcript: audio ? "" : text,
      external_processing_allowed: consent,
    };
    try {
      let result: Meeting;
      if (audio) {
        const form = new FormData();
        form.set("metadata", JSON.stringify(data));
        form.set("file", audio);
        result = await request("/meetings/audio", "POST", form);
      } else result = await request("/meetings", "POST", data);
      created(result.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Besprechung erfassen" close={close}>
      <form onSubmit={submit}>
        <div className="fields">
          <label>
            Titel
            <input required minLength={3} maxLength={160} value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <div className="two">
            <label>
              Besprechungsdatum
              <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
            </label>
            <label>
              Prüfende Person
              <select value={reviewer} onChange={(e) => setReviewer(Number(e.target.value))}>
                {accounts
                  .filter((a) => a.role === "reviewer")
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <label>
            Teilnehmende, mit Komma getrennt
            <input required value={participants} onChange={(e) => setParticipants(e.target.value)} maxLength={3000} />
          </label>
          <div className="fieldhead">
            <span>Notizen / Transkript</span>
            <div className="inline">
              <label className="upload">
                <Upload size={15} /> Textdatei
                <input
                  type="file"
                  accept=".txt"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    if (file.size > 240000) {
                      setError("Die Textdatei ist zu groß.");
                      return;
                    }
                    const value = await file.text();
                    if (value.length > 60000) {
                      setError("Maximal 60.000 Zeichen.");
                      return;
                    }
                    setAudio(null);
                    setText(value);
                  }}
                />
              </label>
              <button
                type="button"
                className="quiet"
                onClick={() => {
                  setTitle(example.title);
                  setParticipants(example.participants);
                  setText(example.transcript);
                  setAudio(null);
                }}
              >
                Beispiel
              </button>
            </div>
          </div>
          <textarea
            aria-label="Notizen oder Transkript"
            required={!audio}
            minLength={30}
            maxLength={60000}
            rows={9}
            value={text}
            onChange={(e) => {
              setAudio(null);
              setText(e.target.value);
            }}
          />
          {meta.provider === "openai" && (
            <label className="upload audio">
              <Upload size={16} />
              {audio ? audio.name : "Aufnahme auswählen (max. 25 MB)"}
              <input
                type="file"
                accept=".wav,.mp3,.m4a,.webm,.ogg"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  if (file && file.size > 25 * 1024 * 1024) {
                    setError("Die Aufnahme ist größer als 25 MB.");
                    return;
                  }
                  setAudio(file);
                }}
              />
              {audio && (
                <button
                  type="button"
                  className="icon"
                  title="Aufnahme entfernen"
                  onClick={(e) => {
                    e.preventDefault();
                    setAudio(null);
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </label>
          )}
          {meta.provider === "openai" && (
            <label className="check">
              <input type="checkbox" checked={consent} required onChange={(e) => setConsent(e.target.checked)} />
              Die erforderlichen Zustimmungen liegen vor. Die Quelle darf zur Verarbeitung an OpenAI übertragen werden.
            </label>
          )}
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <footer>
          <button type="button" onClick={close} disabled={busy}>
            Abbrechen
          </button>
          <button className="primary" disabled={busy}>
            {busy ? <LoaderCircle size={16} className="spin" /> : <ArrowRight size={16} />}
            Entwurf erstellen
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function EditReport({ detail, close, saved }: { detail: Detail; close: () => void; saved: () => void }) {
  const [report, setReport] = useState<Report>(() => structuredClone(detail.editable_report!));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function change(section: Section, index: number, fields: Partial<Entry>) {
    setReport((r) => ({
      ...r,
      [section]: r[section].map((v, i) => (i === index ? { ...v, ...fields } : v)),
    }));
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await request(`/meetings/${detail.meeting.id}/draft`, "PUT", {
        expected_revision: detail.revision,
        report,
      });
      saved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal wide title={`Entwurf bearbeiten · Version ${detail.revision}`} close={close}>
      <form onSubmit={submit}>
        <div className="fields editfields">
          {sections.map((section) => (
            <section key={section}>
              <div className="fieldhead">
                <h3>{labels[section]}</h3>
                <button
                  type="button"
                  className="icon"
                  title="Eintrag ergänzen"
                  onClick={() =>
                    setReport((r) => ({
                      ...r,
                      [section]: [
                        ...r[section],
                        {
                          text: "",
                          source_ids: [1],
                          quote: "",
                          ...(section === "tasks" ? { owner: null, due_text: null } : {}),
                        },
                      ],
                    }))
                  }
                >
                  <Plus size={17} />
                </button>
              </div>
              {report[section].map((item, index) => (
                <div className="editentry" key={index}>
                  <div className="entryhead">
                    <span>{index + 1}</span>
                    <button
                      type="button"
                      className="icon"
                      title="Eintrag entfernen"
                      onClick={() =>
                        setReport((r) => ({
                          ...r,
                          [section]: r[section].filter((_, i) => i !== index),
                        }))
                      }
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                  <label>
                    Inhalt
                    <textarea
                      aria-label="Inhalt"
                      required
                      minLength={3}
                      maxLength={1200}
                      rows={2}
                      value={item.text}
                      onChange={(e) => change(section, index, { text: e.target.value })}
                    />
                  </label>
                  <label>
                    Wörtlicher Textbeleg
                    <textarea
                      aria-label="Wörtlicher Textbeleg"
                      required
                      minLength={5}
                      maxLength={1500}
                      rows={2}
                      value={item.quote}
                      onChange={(e) => change(section, index, { quote: e.target.value })}
                    />
                  </label>
                  <label>
                    Quellenabschnitte
                    <select
                      multiple
                      required
                      value={item.source_ids.map(String)}
                      onChange={(e) =>
                        change(section, index, {
                          source_ids: Array.from(e.target.selectedOptions, (o) => Number(o.value)).slice(0, 5),
                        })
                      }
                    >
                      {detail.source.segments.map((s) => (
                        <option key={s.id} value={s.id}>
                          #{s.id} {s.speaker || "Quelle"}: {s.text.slice(0, 80)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {section === "tasks" && (
                    <div className="two">
                      <label>
                        Verantwortlich
                        <select
                          value={item.owner || ""}
                          onChange={(e) =>
                            change(section, index, {
                              owner: e.target.value || null,
                            })
                          }
                        >
                          <option value="">Nicht benannt</option>
                          {detail.meeting.participants.map((p) => (
                            <option key={p}>{p}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Frist
                        <input
                          maxLength={100}
                          value={item.due_text || ""}
                          onChange={(e) =>
                            change(section, index, {
                              due_text: e.target.value || null,
                            })
                          }
                        />
                      </label>
                    </div>
                  )}
                </div>
              ))}
            </section>
          ))}
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <footer>
          <button type="button" onClick={close} disabled={busy}>
            Abbrechen
          </button>
          <button className="primary" disabled={busy}>
            <Check size={16} />
            Neue Version speichern
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function App() {
  const [meta, setMeta] = useState<Meta>({
    provider: "demo",
    workflow_mode: "local",
    configured: false,
  });
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [user, setUser] = useState<Account | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [tab, setTab] = useState("report");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [focus, setFocus] = useState<number[]>([]);
  const [modal, setModal] = useState<"new" | "edit" | "source" | "changes" | "approve" | null>(null);
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function refresh() {
    if (!user) return;
    setMeetings(await request("/meetings"));
    if (selected) setDetail(await request(`/meetings/${selected}${version ? `?revision=${version}` : ""}`));
  }
  useEffect(() => {
    Promise.all([request<Meta>("/meta"), request<Account[]>("/accounts")])
      .then(([m, a]) => {
        setMeta(m);
        setAccounts(a);
      })
      .catch((e) => setError(e.message));
    request<Account>("/me")
      .then(setUser)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!user) return;
    let active = true;
    const load = async () => {
      try {
        const list = await request<Meeting[]>("/meetings");
        if (active) setMeetings(list);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    load();
    const timer = window.setInterval(load, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [user]);
  useEffect(() => {
    if (!selected || !user) {
      setDetail(null);
      return;
    }
    let active = true;
    const load = async () => {
      try {
        const d = await request<Detail>(`/meetings/${selected}${version ? `?revision=${version}` : ""}`);
        if (active) setDetail(d);
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    load();
    const timer = window.setInterval(load, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selected, version, user]);
  async function login(id: number) {
    try {
      const account = await request<Account>("/login", "POST", {
        account_id: id,
      });
      setSelected(null);
      setVersion(null);
      setDetail(null);
      setMeetings([]);
      setUser(account);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function action(path: string, body?: unknown, method = "POST") {
    setBusy(true);
    setError("");
    try {
      await request(`/meetings/${selected}/${path}`, method, body);
      setModal(null);
      setVersion(null);
      await refresh();
      setNotice("Änderung gespeichert.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openSource() {
    setText(sourceText(detail!.current_source.segments));
    setConsent(false);
    setModal("source");
  }
  function cite(ids: number[]) {
    setFocus(ids);
    setTab("source");
  }
  useEffect(() => {
    if (tab === "source" && focus.length)
      document.getElementById(`source-${focus[0]}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [tab, focus]);
  const current = detail?.meeting;
  const isOwner = user?.id === current?.owner_id;
  const latest = detail?.revision === current?.current_revision;
  const canEdit = isOwner && latest && ["draft", "changes_requested", "approved"].includes(current?.status || "");
  const canReview = user?.id === current?.reviewer_id && current?.status === "review" && latest;
  const visible = meetings.filter(
    (m) =>
      (!filter || m.status === filter) &&
      `${m.title} ${m.participants.join(" ")}`.toLowerCase().includes(query.toLowerCase()),
  );
  function entries(section: Section) {
    return detail?.report?.[section].length ? (
      detail.report[section].map((item, index) => (
        <article className="fact" key={item.id || index}>
          <div className="factnumber">{String(index + 1).padStart(2, "0")}</div>
          <div>
            <p>{item.text}</p>
            {section === "tasks" && (
              <div className="entrymeta">
                <span>{item.owner || "Nicht benannt"}</span>
                <span>{item.due_text || "Keine Frist"}</span>
              </div>
            )}
            <button className="citation" onClick={() => cite(item.source_ids)} title={item.quote}>
              <Quote size={13} />
              {item.source_ids.map((id) => `#${id}`).join(", ")}
            </button>
          </div>
        </article>
      ))
    ) : (
      <p className="emptyline">Keine Einträge.</p>
    );
  }
  const stages = ["Quelle", "Auswertung", "Belege", "Entwurf"];
  const stageIndex =
    (
      {
        pending: -1,
        claimed: 0,
        source_ready: 1,
        extracting: 1,
        extracted: 2,
        validated: 3,
        saved: 4,
      } as Record<string, number>
    )[detail?.processing?.stage || "pending"] ?? -1;
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span>
            <ClipboardList size={22} />
          </span>
          <div>
            Besprechungsprotokolle<small>TEAM WORKSPACE</small>
          </div>
        </div>
        <div className="account">
          <span className="mode">{meta.provider === "demo" ? "Regelbasiert" : "API-Verarbeitung"}</span>
          <label>
            <span className="accountlabel">Lokales Testkonto</span>
            <select aria-label="Konto wechseln" value={user?.id || ""} onChange={(e) => login(Number(e.target.value))}>
              <option value="" disabled>
                Konto wählen
              </option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} · {a.role === "reviewer" ? "Prüfung" : "Erstellung"}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      {error && (
        <div role="alert" className="banner error">
          <AlertCircle size={17} />
          <span>{error}</span>
          <button className="icon" title="Meldung schließen" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {notice && (
        <div role="status" className="banner success">
          <Check size={16} />
          <span>{notice}</span>
          <button className="icon" title="Meldung schließen" onClick={() => setNotice("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {!user ? (
        <main className="login">
          <ClipboardList size={36} />
          <h1>Besprechungsprotokolle</h1>
          <div className="loginaccounts">
            {accounts.map((a) => (
              <button key={a.id} onClick={() => login(a.id)}>
                <div>
                  <strong>{a.name}</strong>
                  <span>{a.role === "reviewer" ? "Prüfende Person" : "Erstellerkonto"}</span>
                </div>
                <ArrowRight size={18} />
              </button>
            ))}
          </div>
        </main>
      ) : (
        <main className={`workspace ${selected ? "hasselection" : ""}`}>
          <aside className="sidebar">
            <div className="sidehead">
              <h1>
                Besprechungen <span>{meetings.length}</span>
              </h1>
              {user.role === "editor" && (
                <button
                  className="icon primary"
                  title="Besprechung erfassen"
                  aria-label="Besprechung erfassen"
                  onClick={() => setModal("new")}
                >
                  <Plus size={18} />
                </button>
              )}
            </div>
            <label className="search">
              <Search size={16} />
              <input
                placeholder="Besprechungen suchen"
                aria-label="Besprechungen suchen"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <select aria-label="Statusfilter" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="">Alle Status</option>
              {Object.entries(statuses).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
            <nav className="meetinglist" aria-label="Besprechungen">
              {visible.map((m) => (
                <button
                  className={`meeting ${selected === m.id ? "selected" : ""}`}
                  key={m.id}
                  onClick={() => {
                    setSelected(m.id);
                    setVersion(null);
                    setDetail(null);
                    setTab("report");
                    setFocus([]);
                    setNotice("");
                  }}
                >
                  <div className="row">
                    <span className={`badge ${m.status}`}>{statuses[m.status]}</span>
                    <time>{m.meeting_date.split("-").reverse().join(".")}</time>
                  </div>
                  <strong>{m.title}</strong>
                  <small>{m.participants.join(" · ")}</small>
                  <span className="revision">
                    {m.current_revision ? `Version ${m.current_revision}` : "Noch kein Entwurf"}
                    <ChevronRight size={13} />
                  </span>
                </button>
              ))}
              {!visible.length && (
                <p className="emptylist">{meetings.length ? "Keine Treffer." : "Noch keine Besprechungen."}</p>
              )}
            </nav>
            <div className="sidefoot">
              <ShieldCheck size={15} />
              {meta.workflow_mode === "n8n" ? "n8n-Workflow" : "Lokale Verarbeitung"}
            </div>
          </aside>
          <section className="content">
            {!selected ? (
              <div className="empty">
                <FileText size={42} />
                <h2>{meetings.length ? "Besprechung auswählen" : "Ein neues Protokoll beginnt hier"}</h2>
                {user.role === "editor" && (
                  <button className="primary" onClick={() => setModal("new")}>
                    <Plus size={17} />
                    Besprechung erfassen
                  </button>
                )}
              </div>
            ) : !detail ? (
              <div className="empty">
                <LoaderCircle className="spin" size={28} />
                <span>Wird geladen</span>
              </div>
            ) : (
              <>
                <div className="contenthead">
                  <button className="icon mobileback" title="Zur Übersicht" onClick={() => setSelected(null)}>
                    <ArrowLeft size={18} />
                  </button>
                  <div className="heading">
                    <div className="eyebrow">
                      {current!.meeting_date.split("-").reverse().join(".")}
                      <span className={`badge ${current!.status}`}>{statuses[current!.status]}</span>
                    </div>
                    <h1>{current!.title}</h1>
                    <p>{current!.participants.join(" · ")}</p>
                  </div>
                  <button
                    className="icon"
                    title="Aktualisieren"
                    aria-label="Aktualisieren"
                    onClick={() => refresh().catch((e) => setError(e.message))}
                  >
                    <RefreshCw size={17} />
                  </button>
                </div>
                <div className="toolbar">
                  <div className="version">
                    <select
                      aria-label="Protokollversion"
                      value={version || ""}
                      onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">
                        Aktueller Stand
                        {current!.current_revision ? ` · V${current!.current_revision}` : ""}
                      </option>
                      {detail.versions.map((v) => (
                        <option key={v.number} value={v.number}>
                          Version {v.number}
                          {v.approved ? " · Freigegeben" : " · Entwurf"}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="actions">
                    {canEdit && (
                      <button disabled={busy} onClick={() => setModal("edit")}>
                        <Pencil size={15} />
                        Bearbeiten
                      </button>
                    )}
                    {canEdit && current!.status !== "approved" && (
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() =>
                          action("submit", {
                            expected_revision: detail.revision,
                          })
                        }
                      >
                        <ArrowRight size={15} />
                        Zur Prüfung
                      </button>
                    )}
                    {canReview && (
                      <>
                        <button
                          disabled={busy}
                          onClick={() => {
                            setText("");
                            setModal("changes");
                          }}
                        >
                          <MessageSquare size={15} />
                          Änderung erbitten
                        </button>
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() => {
                            setConsent(false);
                            setModal("approve");
                          }}
                        >
                          <CheckCheck size={16} />
                          Freigeben
                        </button>
                      </>
                    )}
                    {detail.approved && (
                      <>
                        <a className="button" href={`/api/meetings/${selected}/export/md?revision=${detail.revision}`}>
                          <Download size={15} />
                          Protokoll
                        </a>
                        <a className="button" href={`/api/meetings/${selected}/export/csv?revision=${detail.revision}`}>
                          <Download size={15} />
                          Aufgaben
                        </a>
                      </>
                    )}
                  </div>
                </div>
                {detail.approved && (
                  <div className="approval">
                    <ShieldCheck size={17} />
                    Version {detail.revision} · Freigegeben von {detail.approved_by}
                    <span>{detail.approved_at ? new Date(detail.approved_at).toLocaleString("de-DE") : ""}</span>
                  </div>
                )}
                {current!.status === "error" && (
                  <div className="banner error">
                    <AlertCircle size={17} />
                    <span>{current!.last_error}</span>
                    {isOwner && (
                      <button onClick={() => action("retry")} disabled={busy}>
                        <RefreshCw size={15} />
                        Erneut versuchen
                      </button>
                    )}
                  </div>
                )}
                {["queued", "processing"].includes(current!.status) && (
                  <div className="processing" role="status">
                    {stages.map((stage, i) => (
                      <span key={stage} className={i < stageIndex ? "done" : i === stageIndex ? "active" : ""}>
                        {i < stageIndex ? (
                          <Check size={15} />
                        ) : i === stageIndex ? (
                          <LoaderCircle size={15} className="spin" />
                        ) : (
                          <span className="stepnum">{i + 1}</span>
                        )}
                        {stage}
                      </span>
                    ))}
                  </div>
                )}
                <nav className="tabs" aria-label="Ansichten">
                  {[
                    ["report", "Protokoll", FileText],
                    ["source", "Transkript", Quote],
                    ["tasks", "Aufgaben", ListChecks],
                    ["history", "Verlauf", History],
                  ].map(([key, label, Icon]) => {
                    const Symbol = Icon as typeof FileText;
                    return (
                      <button
                        key={key as string}
                        className={tab === key ? "active" : ""}
                        aria-current={tab === key ? "page" : undefined}
                        onClick={() => setTab(key as string)}
                      >
                        <Symbol size={16} />
                        {label as string}
                        {key === "tasks" && <span>{detail.report?.tasks.length || 0}</span>}
                      </button>
                    );
                  })}
                </nav>
                <div className="tabcontent">
                  {tab === "report" &&
                    (!detail.report ? (
                      <div className="empty compact">
                        <FileText size={28} />
                        <h2>
                          {current!.status === "error" ? "Noch kein Entwurf vorhanden" : "Protokoll wird vorbereitet"}
                        </h2>
                      </div>
                    ) : (
                      <>
                        <div className="reportmeta">
                          <span>Quelle {detail.source.version}</span>
                          <span>Erstellt von {current!.owner_name}</span>
                          <span>Prüfung: {current!.reviewer_name}</span>
                        </div>
                        {!!detail.report.warnings?.length && (
                          <div className="warnings">
                            <AlertCircle size={17} />
                            <ul>
                              {detail.report.warnings.map((w, i) => (
                                <li key={i}>{w}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {sections
                          .filter((s) => s !== "tasks")
                          .map((section) => (
                            <section className="reportsection" key={section}>
                              <h2>
                                {labels[section]}
                                <span>{detail.report![section].length}</span>
                              </h2>
                              {entries(section)}
                            </section>
                          ))}
                      </>
                    ))}
                  {tab === "source" && (
                    <>
                      <div className="fieldhead">
                        <h2>Quelle {detail.source.version}</h2>
                        {isOwner && (
                          <button disabled={busy} onClick={openSource}>
                            <Pencil size={15} />
                            Quelle ersetzen
                          </button>
                        )}
                      </div>
                      <div className="transcript">
                        {detail.source.segments.map((s) => (
                          <article id={`source-${s.id}`} className={focus.includes(s.id) ? "highlight" : ""} key={s.id}>
                            <span className="sourceid">#{s.id}</span>
                            <div>
                              <header>
                                <strong>{s.speaker || "Quelle"}</strong>
                                <time>{s.timestamp}</time>
                              </header>
                              <p>{s.text}</p>
                            </div>
                          </article>
                        ))}
                      </div>
                    </>
                  )}
                  {tab === "tasks" && (
                    <>
                      <div className="fieldhead">
                        <h2>
                          Aufgaben <span className="count">{detail.report?.tasks.length || 0}</span>
                        </h2>
                        <span className="muted">Version {detail.revision || "–"}</span>
                      </div>
                      <div className="tasklist">
                        {detail.report?.tasks.map((t) => (
                          <article className="task" key={t.id}>
                            <div>
                              <strong>{t.text}</strong>
                              <div className="entrymeta">
                                <span>{t.owner || "Nicht benannt"}</span>
                                <span>{t.due_text || "Keine Frist"}</span>
                                <button className="citation" onClick={() => cite(t.source_ids)}>
                                  <Quote size={13} />
                                  {t.source_ids.map((id) => `#${id}`).join(", ")}
                                </button>
                              </div>
                            </div>
                            {detail.approved ? (
                              <select
                                aria-label={`Status ${t.id}`}
                                value={detail.task_states[t.id!] || "open"}
                                disabled={busy}
                                onChange={(e) =>
                                  action(
                                    `tasks/${t.id}`,
                                    {
                                      revision: detail.revision,
                                      status: e.target.value,
                                    },
                                    "PUT",
                                  )
                                }
                              >
                                <option value="open">Offen</option>
                                <option value="in_progress">In Arbeit</option>
                                <option value="done">Erledigt</option>
                              </select>
                            ) : (
                              <span className="badge draft">Nicht freigegeben</span>
                            )}
                          </article>
                        ))}
                        {!detail.report?.tasks.length && (
                          <p className="emptyline">Keine vereinbarten Aufgaben erfasst.</p>
                        )}
                      </div>
                    </>
                  )}
                  {tab === "history" && (
                    <ol className="timeline">
                      {[...detail.events].reverse().map((e) => (
                        <li key={e.id}>
                          <span />
                          <div>
                            <p>{e.description}</p>
                            <small>
                              {e.actor} · {new Date(e.created_at).toLocaleString("de-DE")}
                            </small>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </>
            )}
          </section>
        </main>
      )}
      {modal === "new" && (
        <NewMeeting
          meta={meta}
          accounts={accounts}
          close={() => setModal(null)}
          created={(id) => {
            setSelected(id);
            setVersion(null);
            setDetail(null);
            setTab("report");
            setModal(null);
            refresh().catch((e) => setError(e.message));
          }}
        />
      )}
      {modal === "edit" && detail && (
        <EditReport
          detail={detail}
          close={() => setModal(null)}
          saved={() => {
            setModal(null);
            setVersion(null);
            refresh().catch((e) => setError(e.message));
          }}
        />
      )}
      {modal === "source" && detail && (
        <Modal title="Neue Quelle erfassen" close={() => setModal(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              action(
                "source",
                {
                  expected_source_version: current!.source_version,
                  transcript: text,
                  external_processing_allowed: consent,
                },
                "PUT",
              );
            }}
          >
            <div className="fields">
              <label>
                Notizen / Transkript
                <textarea
                  required
                  minLength={30}
                  maxLength={60000}
                  rows={12}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </label>
              {meta.provider === "openai" && (
                <label className="check">
                  <input type="checkbox" checked={consent} required onChange={(e) => setConsent(e.target.checked)} />
                  Die Quelle ist zur externen Verarbeitung freigegeben.
                </label>
              )}
            </div>
            <footer>
              <button type="button" disabled={busy} onClick={() => setModal(null)}>
                Abbrechen
              </button>
              <button className="primary" disabled={busy}>
                <RefreshCw size={16} />
                Neu verarbeiten
              </button>
            </footer>
          </form>
        </Modal>
      )}
      {modal === "changes" && detail && (
        <Modal title="Änderungen erbitten" close={() => setModal(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              action("request-changes", {
                expected_revision: detail.revision,
                note: text,
              });
            }}
          >
            <div className="fields">
              <label>
                Prüfvermerk
                <textarea
                  required
                  minLength={5}
                  maxLength={1000}
                  rows={5}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </label>
            </div>
            <footer>
              <button type="button" onClick={() => setModal(null)}>
                Abbrechen
              </button>
              <button className="primary" disabled={busy}>
                <ArrowLeft size={16} />
                Zurück an Erstellung
              </button>
            </footer>
          </form>
        </Modal>
      )}
      {modal === "approve" && detail && (
        <Modal title={`Version ${detail.revision} freigeben`} close={() => setModal(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              action("approve", {
                expected_revision: detail.revision,
                acknowledge_warnings: consent,
              });
            }}
          >
            <div className="fields">
              <p className="approvalstatement">{current!.title}</p>
              <label className="check">
                <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                Ich habe Inhalte, Quellenbelege, Aufgaben und mögliche Prüfhinweise geprüft und gebe diese Version frei.
              </label>
            </div>
            <footer>
              <button type="button" onClick={() => setModal(null)}>
                Abbrechen
              </button>
              <button className="primary" disabled={busy || !consent}>
                <ShieldCheck size={16} />
                Verbindlich freigeben
              </button>
            </footer>
          </form>
        </Modal>
      )}
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
