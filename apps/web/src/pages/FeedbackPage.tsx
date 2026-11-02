import {
  FEEDBACK_CATEGORIES,
  FEEDBACK_CATEGORY_LABEL,
  FEEDBACK_MAX_ATTACHMENTS,
  FEEDBACK_MESSAGE_MAX_CHARS,
  FEEDBACK_MESSAGE_MIN_CHARS,
  FEEDBACK_STATUS_LABEL,
  feedbackAttachmentKind,
  validateFeedbackDraft,
  type FeedbackCategory,
  type FeedbackReportSummary,
} from "@fantappero/contracts";
import {
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  PageContainer,
  Select,
  Textarea,
  UiStatePanel,
} from "@fantappero/ui";
import { type ChangeEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { fetchMyFeedback, sendFeedback } from "../api/feedback";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { readLastAppPath } from "../feedback/lastPage";

const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime,video/webm";

const CATEGORY_OPTIONS = FEEDBACK_CATEGORIES.map((value) => ({
  value,
  label: FEEDBACK_CATEGORY_LABEL[value],
}));

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat("it-IT", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Rome",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

type Picked = { key: string; file: File; previewUrl: string | null };

function AttachmentPreview({ item, onRemove }: { item: Picked; onRemove: () => void }) {
  const kind = feedbackAttachmentKind(item.file.type);
  return (
    <li className="fa-feedback__file" data-testid="feedback-file">
      {item.previewUrl && kind === "image" ? (
        <img className="fa-feedback__thumb" src={item.previewUrl} alt="" />
      ) : (
        <span className="fa-feedback__thumb fa-feedback__thumb--video" aria-hidden="true">
          ▶
        </span>
      )}
      <span className="fa-feedback__file-meta">
        <strong>{item.file.name}</strong>
        <small>
          {kind === "video" ? "Video" : "Immagine"} · {formatSize(item.file.size)}
        </small>
      </span>
      <Button type="button" variant="ghost" onClick={onRemove} aria-label={`Rimuovi ${item.file.name}`}>
        Rimuovi
      </Button>
    </li>
  );
}

/** «Segnala un problema»: il tester descrive il bug e può allegare uno screenshot o un video. */
export function FeedbackPage() {
  const { isDemoMode } = useAuth();
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [message, setMessage] = useState("");
  const [picked, setPicked] = useState<Picked[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);
  const [mine, setMine] = useState<FeedbackReportSummary[]>([]);
  const [mineError, setMineError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pickedRef = useRef<Picked[]>([]);
  pickedRef.current = picked;

  const loadMine = useCallback(async () => {
    if (isDemoMode) {
      return;
    }
    const token = loadStoredSession()?.accessToken;
    if (!token) {
      return;
    }
    try {
      setMine(await fetchMyFeedback(token));
      setMineError(null);
    } catch (loadError) {
      setMineError(getApiErrorMessage(loadError, "Impossibile caricare le tue segnalazioni."));
    }
  }, [isDemoMode]);

  useEffect(() => {
    void loadMine();
  }, [loadMine]);

  // Libera le anteprime create con createObjectURL quando si esce dalla pagina.
  useEffect(
    () => () => {
      for (const item of pickedRef.current) {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl);
        }
      }
    },
    [],
  );

  function onPickFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (files.length === 0) {
      return;
    }
    const next = [
      ...picked,
      ...files.map((file) => ({
        key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        previewUrl: feedbackAttachmentKind(file.type) === "image" ? URL.createObjectURL(file) : null,
      })),
    ];
    setSent(false);
    const problem = validateFeedbackDraft({
      message: "x".repeat(FEEDBACK_MESSAGE_MIN_CHARS),
      attachments: next.map((item) => ({
        name: item.file.name,
        mimeType: item.file.type,
        sizeBytes: item.file.size,
      })),
    });
    if (problem) {
      for (const item of next.slice(picked.length)) {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl);
        }
      }
      setError(problem);
      return;
    }
    setError(null);
    setPicked(next);
  }

  function removeFile(key: string) {
    setPicked((current) => {
      const removed = current.find((item) => item.key === key);
      if (removed?.previewUrl) {
        URL.revokeObjectURL(removed.previewUrl);
      }
      return current.filter((item) => item.key !== key);
    });
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSent(false);
    const problem = validateFeedbackDraft({
      message,
      attachments: picked.map((item) => ({
        name: item.file.name,
        mimeType: item.file.type,
        sizeBytes: item.file.size,
      })),
    });
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setSending(true);
    try {
      if (!isDemoMode) {
        const token = loadStoredSession()?.accessToken;
        if (!token) {
          throw new Error("Sessione non disponibile. Accedi di nuovo.");
        }
        await sendFeedback(token, {
          message,
          category,
          pageContext: readLastAppPath(),
          files: picked.map((item) => item.file),
        });
      }
      for (const item of picked) {
        if (item.previewUrl) {
          URL.revokeObjectURL(item.previewUrl);
        }
      }
      setPicked([]);
      setMessage("");
      setSent(true);
      void loadMine();
    } catch (submitError) {
      setError(getApiErrorMessage(submitError, "Invio non riuscito. Riprova tra poco."));
    } finally {
      setSending(false);
    }
  }

  const remaining = FEEDBACK_MAX_ATTACHMENTS - picked.length;
  const hasVideo = picked.some((item) => feedbackAttachmentKind(item.file.type) === "video");

  return (
    <PageContainer
      title="Segnala un problema"
      header={<Breadcrumb items={[{ label: "Profilo", href: "/profilo" }, { label: "Segnala un problema" }]} />}
    >
      <p className="fa-feedback__intro">
        Hai trovato un bug o hai un'idea? Raccontacelo: ci aiuta a sistemare l'app. Se puoi, aggiungi
        uno screenshot o un breve video che mostra il problema.
      </p>

      <form className="fa-feedback" onSubmit={(event) => void onSubmit(event)} data-testid="feedback-form">
        <Select
          label="Di cosa si tratta?"
          name="category"
          value={category}
          onChange={(event) => setCategory(event.target.value as FeedbackCategory)}
          options={CATEGORY_OPTIONS}
        />

        <Textarea
          label="Cosa è successo?"
          name="message"
          value={message}
          maxLength={FEEDBACK_MESSAGE_MAX_CHARS}
          onChange={(event) => {
            setMessage(event.target.value);
            setSent(false);
          }}
          placeholder="Cosa stavi facendo, cosa ti aspettavi e cosa è successo invece."
          hint={`${message.trim().length}/${FEEDBACK_MESSAGE_MAX_CHARS} caratteri (almeno ${FEEDBACK_MESSAGE_MIN_CHARS})`}
          data-testid="feedback-message"
        />

        <div className="fa-field">
          <span className="fa-field__label">Immagine o video (facoltativo)</span>
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={onPickFiles}
            data-testid="feedback-file-input"
          />
          <div>
            <Button
              type="button"
              variant="secondary"
              disabled={remaining <= 0 || sending}
              onClick={() => fileInput.current?.click()}
              data-testid="feedback-add-file"
            >
              Aggiungi immagine o video
            </Button>
          </div>
          <p className="fa-field__hint">
            Fino a {FEEDBACK_MAX_ATTACHMENTS} file: immagini fino a 8 MB, video fino a 50 MB.
          </p>
          {picked.length > 0 ? (
            <ul className="fa-feedback__files" data-testid="feedback-files">
              {picked.map((item) => (
                <AttachmentPreview key={item.key} item={item} onRemove={() => removeFile(item.key)} />
              ))}
            </ul>
          ) : null}
        </div>

        {error ? (
          <UiStatePanel state="error" title="Segnalazione non inviata" message={error} testId="feedback-error" />
        ) : null}
        {sent ? (
          <UiStatePanel
            state="success"
            title="Grazie, segnalazione inviata"
            message="Gli operatori l'hanno ricevuta. Qui sotto vedi lo stato di lavorazione."
            testId="feedback-sent"
          />
        ) : null}

        <div>
          <Button type="submit" loading={sending} disabled={sending} data-testid="feedback-submit">
            {sending ? (hasVideo ? "Caricamento del video…" : "Invio…") : "Invia segnalazione"}
          </Button>
        </div>
      </form>

      <Card>
        <CardHeader>Le tue segnalazioni</CardHeader>
        <CardBody>
          {mineError ? (
            <UiStatePanel state="error" title="Elenco non disponibile" message={mineError} testId="feedback-mine-error" />
          ) : mine.length === 0 ? (
            <p className="fa-feedback__empty" data-testid="feedback-mine-empty">
              Non hai ancora inviato segnalazioni.
            </p>
          ) : (
            <ul className="fa-feedback__mine" data-testid="feedback-mine">
              {mine.map((report) => (
                <li key={report.id} className="fa-feedback__row">
                  <span className={`fa-feedback__status fa-feedback__status--${report.status}`}>
                    {FEEDBACK_STATUS_LABEL[report.status]}
                  </span>
                  <span className="fa-feedback__row-text">
                    <strong>{FEEDBACK_CATEGORY_LABEL[report.category]}</strong>
                    <span>{report.message}</span>
                    <small>
                      {formatDate(report.createdAt)}
                      {report.attachmentCount > 0 ? ` · ${report.attachmentCount} allegat${report.attachmentCount === 1 ? "o" : "i"}` : ""}
                    </small>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </PageContainer>
  );
}
