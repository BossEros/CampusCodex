import { useEffect, useRef, useState } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const STARTER_QUESTIONS = [
  "What are the requirements for transfer students?",
  "What are the requirements for latin honors?",
  "What are the rules on student absences?",
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
    .replace(/([^\n])\s(?=[*-]\s)/g, "$1\n")
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

function getSourceLabel(source, index) {
  if (source.page_number) {
    return `Source ${index + 1} · Page ${source.page_number}`;
  }

  return `Source ${index + 1}`;
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

    if (/^[*-]\s+/.test(line)) {
      const items = [];

      while (index < lines.length && /^[*-]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[*-]\s+/, ""));
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

      if (/^\d+\.\s+/.test(currentLine) || /^[*-]\s+/.test(currentLine)) {
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

function SparkleIcon({ size, className }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 1L9.8 6.2L15 8L9.8 9.8L8 15L6.2 9.8L1 8L6.2 6.2L8 1Z" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 13V3M8 3L3.5 7.5M8 3L12.5 7.5" />
    </svg>
  );
}

function TypingIndicator() {
  return (
    <div className="assistant-row typing-row">
      <div className="assistant-avatar">
        <SparkleIcon size={13} className="assistant-avatar-icon" />
      </div>
      <div className="typing-dots" role="status" aria-label="Assistant is typing">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  );
}

function CitationChip({ message, source, index, openCitation, onToggle }) {
  const isOpen =
    openCitation?.messageId === message.id && openCitation?.sourceIndex === index;

  return (
    <span className="citation-chip-wrapper">
      <button
        type="button"
        className={`citation-chip ${isOpen ? "active" : ""}`}
        onClick={() => onToggle(message.id, index)}
        aria-expanded={isOpen}
        aria-label={`Citation ${index + 1}`}
      >
        {index + 1}
      </button>
      {isOpen ? (
        <span className="citation-popover" role="tooltip">
          <span className="citation-popover-title">{getSourceLabel(source, index)}</span>
          <span className="citation-popover-meta">
            {source.page_number ? `Page ${source.page_number} · ` : ""}
            Score {Number(source.score).toFixed(3)}
          </span>
          <span className="citation-popover-excerpt">&ldquo;{source.excerpt}&rdquo;</span>
        </span>
      ) : null}
    </span>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [openCitation, setOpenCitation] = useState(null);
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

  function toggleCitation(messageId, sourceIndex) {
    setOpenCitation((currentOpenCitation) =>
      currentOpenCitation?.messageId === messageId &&
      currentOpenCitation?.sourceIndex === sourceIndex
        ? null
        : { messageId, sourceIndex }
    );
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
    setOpenCitation(null);
    setIsSending(true);
    setMessages((currentMessages) => [...currentMessages, userMessage]);

    try {
      const data = await fetchJson("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          history: messages.map((message) => ({
            role: message.role,
            content: message.content,
          })),
        }),
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

  function handleComposerKeyDown(event) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    void handleSubmit(question);
  }

  function getIndexStatusText() {
    if (isLoadingStatus) {
      return "Checking index...";
    }

    if (statusError || !indexStatus?.index_loaded) {
      return "Index unavailable";
    }

    return "Index ready";
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-mark">
          <SparkleIcon size={14} />
        </div>
        <div className="brand-copy">
          <p className="brand-wordmark">Nimbus</p>
          <p className="brand-subtitle">Docs Assistant</p>
        </div>
        <p className="index-status-text">{getIndexStatusText()}</p>
      </header>

      <div ref={messageListRef} className="message-list">
        {messages.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-copy">
              Ask a question about the indexed documents to get started.
            </p>
            <div className="starter-chip-list">
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
          messages.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="message-row user-row">
                <p className="user-bubble">{message.content}</p>
              </div>
            ) : (
              <div key={message.id} className="message-row assistant-row">
                <div className="assistant-avatar">
                  <SparkleIcon size={13} className="assistant-avatar-icon" />
                </div>
                <div className="assistant-content">
                  <FormattedMessage content={message.content} />
                  {message.sources?.length ? (
                    <span className="citation-chip-list">
                      {message.sources.map((source, index) => (
                        <CitationChip
                          key={`${message.id}-source-${index}`}
                          message={message}
                          source={source}
                          index={index}
                          openCitation={openCitation}
                          onToggle={toggleCitation}
                        />
                      ))}
                    </span>
                  ) : null}
                </div>
              </div>
            )
          )
        )}

        {isSending ? <TypingIndicator /> : null}
      </div>

      {statusError ? <p className="banner error status-banner">{statusError}</p> : null}
      {chatError ? <p className="banner error chat-banner">{chatError}</p> : null}

      <div className="composer-dock">
        <form className="composer" onSubmit={handleFormSubmit}>
          <div className="composer-pill">
            <textarea
              id="question"
              ref={composerInputRef}
              className="composer-input"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Example: What documents does a transferee need to submit?"
              rows={1}
              disabled={isSending}
            />
            <button
              type="submit"
              className="send-button"
              disabled={isSending || !question.trim()}
              aria-label="Send message"
            >
              <SendIcon />
            </button>
          </div>
          <p className="composer-hint">
            Answers are grounded in indexed internal docs. Click a citation number
            for its source.
          </p>
        </form>
      </div>
    </div>
  );
}
