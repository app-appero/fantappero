/**
 * Segnalazioni degli utenti (bug, suggerimenti) con immagini o video.
 *
 * I limiti rispecchiano quelli del backend (`feedback_settings.py`): il client li
 * controlla prima dell'invio per dare un errore chiaro senza caricare file
 * inutilmente, ma il backend li ri-verifica sempre.
 */

export type FeedbackCategory = "bug" | "suggerimento" | "altro";
export type FeedbackStatus = "new" | "in_review" | "resolved" | "dismissed";
export type FeedbackPlatform = "web" | "android" | "ios";

export const FEEDBACK_MESSAGE_MIN_CHARS = 10;
export const FEEDBACK_MESSAGE_MAX_CHARS = 2000;
export const FEEDBACK_NOTE_MAX_CHARS = 2000;
export const FEEDBACK_MAX_ATTACHMENTS = 3;
export const FEEDBACK_IMAGE_MAX_BYTES = 8 * 1024 * 1024;
export const FEEDBACK_VIDEO_MAX_BYTES = 50 * 1024 * 1024;

export const FEEDBACK_CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  bug: "Problema / bug",
  suggerimento: "Suggerimento",
  altro: "Altro",
};

export const FEEDBACK_STATUS_LABEL: Record<FeedbackStatus, string> = {
  new: "Ricevuta",
  in_review: "In lavorazione",
  resolved: "Risolta",
  dismissed: "Chiusa",
};

export const FEEDBACK_CATEGORIES: readonly FeedbackCategory[] = ["bug", "suggerimento", "altro"];
export const FEEDBACK_STATUSES: readonly FeedbackStatus[] = [
  "new",
  "in_review",
  "resolved",
  "dismissed",
];

/** Segnalazione vista dal suo autore: niente dati interni degli operatori. */
export interface FeedbackReportSummary {
  id: string;
  category: FeedbackCategory;
  message: string;
  status: FeedbackStatus;
  createdAt: string;
  attachmentCount: number;
}

export interface FeedbackAttachment {
  id: string;
  kind: "image" | "video";
  contentType: string;
  sizeBytes: number;
  /** Link firmato e a scadenza (path relativo all'API): apribile da <img>, <video> e dal browser. */
  url: string;
}

export interface FeedbackAdminReport {
  id: string;
  category: FeedbackCategory;
  message: string;
  status: FeedbackStatus;
  createdAt: string;
  authorUserId: string;
  authorName: string;
  authorEmail: string;
  pageContext: string | null;
  platform: FeedbackPlatform | null;
  appVersion: string | null;
  userAgent: string | null;
  operatorNote: string | null;
  handledAt: string | null;
  attachments: FeedbackAttachment[];
}

export interface FeedbackAdminList {
  items: FeedbackAdminReport[];
  total: number;
  /** Quante segnalazioni sono ancora da leggere, indipendentemente dal filtro. */
  newCount: number;
  page: number;
  pageSize: number;
}

export interface FeedbackUpdate {
  status?: FeedbackStatus;
  operatorNote?: string;
}

/** Un file scelto dall'utente, in forma indipendente dalla piattaforma (web `File` o mobile). */
export interface FeedbackAttachmentDraft {
  name: string;
  mimeType: string | null | undefined;
  sizeBytes: number | null | undefined;
}

const IMAGE_MIME = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const VIDEO_MIME = new Set(["video/mp4", "video/quicktime", "video/webm"]);

export function feedbackAttachmentKind(
  mimeType: string | null | undefined,
): "image" | "video" | null {
  const mime = (mimeType ?? "").toLowerCase();
  if (IMAGE_MIME.has(mime)) {
    return "image";
  }
  if (VIDEO_MIME.has(mime)) {
    return "video";
  }
  return null;
}

function megabytes(bytes: number): string {
  return `${Math.round(bytes / (1024 * 1024))} MB`;
}

/** `null` se il file va bene, altrimenti il motivo da mostrare all'utente. */
export function validateFeedbackAttachment(file: FeedbackAttachmentDraft): string | null {
  const kind = feedbackAttachmentKind(file.mimeType);
  if (!kind) {
    return `«${file.name}»: formato non supportato. Usa immagini JPEG, PNG, WebP, GIF o video MP4, MOV, WebM.`;
  }
  const limit = kind === "image" ? FEEDBACK_IMAGE_MAX_BYTES : FEEDBACK_VIDEO_MAX_BYTES;
  if (file.sizeBytes != null && file.sizeBytes > limit) {
    return `«${file.name}»: supera il peso massimo di ${megabytes(limit)} per ${kind === "image" ? "le immagini" : "i video"}.`;
  }
  return null;
}

/** Errore del modulo (testo, allegati) o `null` se si può inviare. */
export function validateFeedbackDraft(draft: {
  message: string;
  attachments: readonly FeedbackAttachmentDraft[];
}): string | null {
  const length = draft.message.trim().length;
  if (length < FEEDBACK_MESSAGE_MIN_CHARS) {
    return `Descrivi il problema in almeno ${FEEDBACK_MESSAGE_MIN_CHARS} caratteri.`;
  }
  if (length > FEEDBACK_MESSAGE_MAX_CHARS) {
    return `Il testo supera i ${FEEDBACK_MESSAGE_MAX_CHARS} caratteri.`;
  }
  if (draft.attachments.length > FEEDBACK_MAX_ATTACHMENTS) {
    return `Puoi allegare al massimo ${FEEDBACK_MAX_ATTACHMENTS} file.`;
  }
  for (const file of draft.attachments) {
    const problem = validateFeedbackAttachment(file);
    if (problem) {
      return problem;
    }
  }
  return null;
}
