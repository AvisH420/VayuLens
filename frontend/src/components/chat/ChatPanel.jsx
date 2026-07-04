// Assistant drawer: grounded Q&A (POST /chat, mocked) with citations and
// confidence, plus the multi-language citizen advisory view.

import { useEffect, useRef, useState } from "react";
import { postChat } from "../../lib/api.js";
import { ADVISORIES } from "../../lib/mock.js";

const SUGGESTIONS = [
  "Why is Anand Vihar severe today?",
  "Which sites should be inspected first?",
  "What does GRAP Stage III mandate?",
  "Advisory for schools today?",
];

export default function ChatPanel({ city, onClose }) {
  const [tab, setTab] = useState("ask");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("en");
  const logRef = useRef(null);

  const advisory = ADVISORIES[city.cfg.id];
  const langs = Object.keys(advisory);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const ask = async (q) => {
    const query = q ?? input.trim();
    if (!query || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: query }]);
    setBusy(true);
    const a = await postChat(query);
    setBusy(false);
    setMessages((m) => [...m, { role: "assistant", ...a }]);
  };

  return (
    <aside className="drawer drawer-right glass">
      <div className="drawer-head">
        <div className="chat-tabs">
          <button className={tab === "ask" ? "active" : ""} onClick={() => setTab("ask")}>
            Ask
          </button>
          <button className={tab === "advisory" ? "active" : ""} onClick={() => setTab("advisory")}>
            Advisory
          </button>
        </div>
        <button className="drawer-close" onClick={onClose} aria-label="Close assistant">×</button>
      </div>

      {tab === "ask" ? (
        <>
          <p className="drawer-sub">
            Grounded on GRAP, NCAP and CPCB SOPs (mock corpus). Cites its
            passages; abstains when retrieval is weak.
          </p>
          <div className="chat-log" ref={logRef}>
            {messages.length === 0 && (
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            )}
            {messages.map((m, i) =>
              m.role === "user" ? (
                <div className="msg msg-user" key={i}>{m.text}</div>
              ) : (
                <div className={`msg msg-ai ${m.abstained ? "abstained" : ""}`} key={i}>
                  <p>{m.text}</p>
                  {m.citations.length > 0 && (
                    <div className="msg-cites">
                      {m.citations.map((c, j) => (
                        <span className="chip" key={j}>{c.doc} · {c.ref}</span>
                      ))}
                    </div>
                  )}
                  <div className="msg-conf">
                    <span>Confidence</span>
                    <div className="meter"><span style={{ width: `${m.confidence * 100}%` }} /></div>
                    <span>{m.confidence.toFixed(2)} · {m.retrieved} passage{m.retrieved !== 1 ? "s" : ""}</span>
                  </div>
                </div>
              )
            )}
            {busy && <div className="msg msg-ai msg-typing">Retrieving…</div>}
          </div>
          <form
            className="chat-input"
            onSubmit={(e) => {
              e.preventDefault();
              ask();
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask about ${city.cfg.name}'s air…`}
              aria-label="Ask the assistant"
            />
            <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}>
              Ask
            </button>
          </form>
        </>
      ) : (
        <div className="advisory">
          <div className="chat-tabs lang-tabs">
            {langs.map((l) => (
              <button key={l} className={lang === l ? "active" : ""} onClick={() => setLang(l)}>
                {l === "en" ? "English" : l === "hi" ? "हिन्दी" : "कोंकणी"}
              </button>
            ))}
          </div>
          <h4 className="advisory-headline">{advisory[lang].headline}</h4>
          <p className="advisory-body">{advisory[lang].body}</p>
          <ul className="advisory-groups">
            {advisory[lang].groups.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
          <p className="advisory-note">
            Ward-level advisories are generated from the live grid and the
            vulnerable-population register. Demo strings for now.
          </p>
        </div>
      )}
    </aside>
  );
}
