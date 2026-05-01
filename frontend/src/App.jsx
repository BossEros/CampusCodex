import { useEffect, useRef, useState } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const STARTER_QUESTIONS = [
  "What are the requirements for transfer students?",
  "What services does the Guidance and Counseling Office provide?",
  "What happens if a student commits theft?",
];

function formatErrorMessage(error) {
  if (error instanceof Error) {
    return error.message;
  }

  return "Something went wrong while talking to the API.";
}

function normalizeMessageContent(content) {
  return content
    .replace(/\r\n/g, "\n")
    .replace(/([^\n])\s(?=\d+\.\s)/g, "$1\n")
    .replace(/([^\n])\s(?=\*\s)/g, "$1\n")
    .replace(/([^\n])\s(?=Additionally,)/g, "$1\n\n")
    .replace(/([^\n])\s(?=Note that)/g, "$1\n\n")
    .trim();
}

function renderInline(text) {
  return text.split(/(\*\*.*?\*\*)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    }

    return part;
  });
}

function FormattedMessage({ content }) {
  const blocks = [];
  const lines = normalizeMessageContent(content).split("\n");
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();

    if (!line) {
      index += 1;
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items = [];

      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }

      blocks.push({ type: "ordered-list", items });
      continue;
    }

    if (/^\*\s+/.test(line)) {
      const items = [];

      while (index < lines.length && /^\*\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\*\s+/, ""));
        index += 1;
      }

      blocks.push({ type: "unordered-list", items });
      continue;
    }

    const paragraphLines = [];

    while (index < lines.length) {
      const currentLine = lines[index].trim();

      if (!currentLine) {
        index += 1;
        break;
      }

      if (/^\d+\.\s+/.test(currentLine) || /^\*\s+/.test(currentLine)) {
        break;
      }

      paragraphLines.push(currentLine);
      index += 1;
    }

    blocks.push({ type: "paragraph", text: paragraphLines.join(" ") });
  }

  return (
    <div className="formatted-copy">
      {blocks.map((block, blockIndex) => {
        if (block.type === "ordered-list") {
          return (
            <ol key={`ordered-${blockIndex}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`ordered-item-${blockIndex}-${itemIndex}`}>
                  {renderInline(item)}
                </li>
              ))}
            </ol>
          );
        }

        if (block.type === "unordered-list") {
          return (
            <ul key={`unordered-${blockIndex}`}>
              {block.items.map((item, itemIndex) => (
                <li key={`unordered-item-${blockIndex}-${itemIndex}`}>
                  {renderInline(item)}
                </li>
              ))}
            </ul>
          );
        }

        return <p key={`paragraph-${blockIndex}`}>{renderInline(block.text)}</p>;
      })}
    </div>
  );
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      typeof data?.detail === "string"
        ? data.detail
        : "Request failed. Please try again.";
    throw new Error(detail);
  }

  return data;
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [activeSources, setActiveSources] = useState([]);
  const [activeEvidenceMessageId, setActiveEvidenceMessageId] = useState("");
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [indexStatus, setIndexStatus] = useState(null);
  const [statusError, setStatusError] = useState("");
  const [chatError, setChatError] = useState("");
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const messageListRef = useRef(null);
  const composerInputRef = useRef(null);

  useEffect(() => {
    let isMounted = true;

    async function loadStatus() {
      try {
        setIsLoadingStatus(true);
        const data = await fetchJson("/api/index/status");

        if (!isMounted) {
          return;
        }

        setIndexStatus(data);
        setStatusError("");
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setStatusError(formatErrorMessage(error));
      } finally {
        if (isMounted) {
          setIsLoadingStatus(false);
        }
      }
    }

    loadStatus();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const messageList = messageListRef.current;

    if (!messageList) {
      return;
    }

    messageList.scrollTo({
      top: messageList.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isSending]);

  useEffect(() => {
    const textarea = composerInputRef.current;

    if (!textarea) {
      return;
    }

    textarea.style.height = "0px";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [question]);

  function handleAssistantMessageClick(message) {
    if (!message.sources?.length) {
      return;
    }

    setActiveSources(message.sources);
    setActiveEvidenceMessageId(message.id);
    setIsEvidenceOpen(true);
  }

  function handleCloseEvidence() {
    setIsEvidenceOpen(false);
    setActiveEvidenceMessageId("");
  }

  async function handleSubmit(submittedQuestion) {
    const trimmedQuestion = submittedQuestion.trim();
    if (!trimmedQuestion || isSending) {
      return;
    }

    const userMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmedQuestion,
    };

    setQuestion("");
    setChatError("");
    setIsSending(true);
    setMessages((currentMessages) => [...currentMessages, userMessage]);

    try {
      const data = await fetchJson("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: trimmedQuestion }),
      });

      const assistantMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.answer,
        sources: data.sources ?? [],
      };

      setMessages((currentMessages) => [...currentMessages, assistantMessage]);
    } catch (error) {
      setChatError(formatErrorMessage(error));
    } finally {
      setIsSending(false);
    }
  }

  function handleFormSubmit(event) {
    event.preventDefault();
    void handleSubmit(question);
  }

  return (
    <div className="app-shell">
      <div className="backdrop backdrop-left" />
      <div className="backdrop backdrop-right" />

      <div className="layout">
        <aside className="sidebar panel">
          <div className="sidebar-section brand-block">
            <p className="eyebrow">University of Cebu Knowledge Assistant</p>
            <h1>Student Manual RAG Chatbot</h1>
            <p className="hero-copy">
              Ask policy questions, get grounded answers, and keep the full chat
              flow in one focused workspace.
            </p>
          </div>

          <div className="sidebar-section">
            <p className="panel-kicker">System Status</p>
            <div className="status-stack">
              <div className={`status-card ${indexStatus?.index_loaded ? "ok" : ""}`}>
                <span className="status-label">Index</span>
                <span className="status-value">
                  {isLoadingStatus
                    ? "Loading..."
                    : indexStatus?.index_loaded
                      ? "Ready"
                      : "Unavailable"}
                </span>
              </div>

              <div className="status-card">
                <span className="status-label">Embedding</span>
                <span className="status-value">
                  {indexStatus?.embedding_model ?? "Waiting for backend"}
                </span>
              </div>

              <div className="status-card">
                <span className="status-label">Top K</span>
                <span className="status-value">
                  {indexStatus?.retrieval_top_k ?? "--"}
                </span>
              </div>
            </div>
            {statusError ? <p className="banner error sidebar-banner">{statusError}</p> : null}
          </div>
        </aside>

        <main className="main-column">
          <section className="chat-stage">
            {isEvidenceOpen ? (
              <button
                type="button"
                className="evidence-backdrop"
                aria-label="Close evidence panel"
                onClick={handleCloseEvidence}
              />
            ) : null}

            <div ref={messageListRef} className="message-list">
              {messages.length === 0 ? (
                <div className="quick-start-card">
                  <p className="panel-kicker">Quick Start</p>
                  <h3 className="quick-start-title">Try one of these questions</h3>
                  <p className="quick-start-copy">
                    Start with admissions, student services, discipline, or transfer
                    policies.
                  </p>
                  <div className="starter-grid">
                    {STARTER_QUESTIONS.map((starterQuestion) => (
                      <button
                        key={starterQuestion}
                        type="button"
                        className="starter-chip"
                        onClick={() => void handleSubmit(starterQuestion)}
                        disabled={isSending}
                      >
                        {starterQuestion}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <article
                    key={message.id}
                    className={`message-card ${message.role} ${
                      message.id === activeEvidenceMessageId ? "active-evidence" : ""
                    } ${message.role === "assistant" ? "interactive-message" : ""}`}
                    onClick={() =>
                      message.role === "assistant"
                        ? handleAssistantMessageClick(message)
                        : undefined
                    }
                  >
                    <p className="message-role">
                      {message.role === "user" ? "You" : "Assistant"}
                    </p>
                    {message.role === "assistant" ? (
                      <FormattedMessage content={message.content} />
                    ) : (
                      <p className="message-content">{message.content}</p>
                    )}
                  </article>
                ))
              )}

              {isSending ? (
                <article className="message-card assistant loading-card">
                  <p className="message-role">Assistant</p>
                  <p className="message-content">Looking through the manual...</p>
                </article>
              ) : null}
            </div>

            {chatError ? <p className="banner error chat-banner">{chatError}</p> : null}

            <div className="composer-dock">
              <form className="composer" onSubmit={handleFormSubmit}>
                <textarea
                  id="question"
                  ref={composerInputRef}
                  className="composer-input"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Example: What documents does a transferee need to submit?"
                  rows={1}
                  disabled={isSending}
                />
                <div className="composer-actions">
                  <p className="composer-note">Keep questions specific for better retrieval.</p>
                  <button
                    type="submit"
                    className="submit-button"
                    disabled={isSending || !question.trim()}
                  >
                    {isSending ? "Sending..." : "Ask the manual"}
                  </button>
                </div>
              </form>
            </div>

            <aside className={`evidence-drawer ${isEvidenceOpen ? "open" : ""}`}>
              <div className="evidence-drawer-header">
                <div>
                  <p className="panel-kicker">Evidence</p>
                  <h3 className="evidence-title">Retrieved supporting excerpts</h3>
                </div>
                <button
                  type="button"
                  className="evidence-close"
                  aria-label="Close evidence panel"
                  onClick={handleCloseEvidence}
                >
                  Close
                </button>
              </div>

              {activeSources.length > 0 ? (
                <>
                  <p className="evidence-note">
                    This panel shows the retrieved chunks behind the selected
                    assistant response.
                  </p>
                  <div className="evidence-list">
                    {activeSources.map((source, index) => (
                      <article key={`${source.excerpt}-${index}`} className="evidence-card">
                        <div className="evidence-meta">
                          <span className="status-label">Chunk {index + 1}</span>
                          <span className="evidence-score">
                            Score {Number(source.score).toFixed(3)}
                          </span>
                        </div>
                        <p className="evidence-excerpt">{source.excerpt}</p>
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <div className="evidence-empty">
                  <p className="empty-title">No evidence selected yet.</p>
                  <p className="empty-copy">
                    Click an assistant response to open its retrieved excerpts here.
                  </p>
                </div>
              )}
            </aside>
          </section>
        </main>
      </div>
    </div>
  );
}
