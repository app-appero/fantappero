import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  FEEDBACK_IMAGE_MAX_BYTES,
  FEEDBACK_MAX_ATTACHMENTS,
  FEEDBACK_VIDEO_MAX_BYTES,
  feedbackAttachmentKind,
  validateFeedbackAttachment,
  validateFeedbackDraft,
} from "./feedback.ts";

const message = "Dopo il salvataggio il pulsante resta grigio.";

describe("feedbackAttachmentKind", () => {
  it("riconosce immagini e video, ignorando maiuscole", () => {
    assert.equal(feedbackAttachmentKind("image/PNG"), "image");
    assert.equal(feedbackAttachmentKind("video/quicktime"), "video");
    assert.equal(feedbackAttachmentKind("application/pdf"), null);
    assert.equal(feedbackAttachmentKind(undefined), null);
  });
});

describe("validateFeedbackAttachment", () => {
  it("accetta file nei limiti", () => {
    assert.equal(
      validateFeedbackAttachment({ name: "a.png", mimeType: "image/png", sizeBytes: 1000 }),
      null,
    );
  });

  it("applica limiti diversi a immagini e video", () => {
    const size = FEEDBACK_IMAGE_MAX_BYTES + 1;
    assert.match(
      validateFeedbackAttachment({ name: "a.png", mimeType: "image/png", sizeBytes: size }) ?? "",
      /peso massimo di 8 MB per le immagini/,
    );
    assert.equal(
      validateFeedbackAttachment({ name: "a.mp4", mimeType: "video/mp4", sizeBytes: size }),
      null,
    );
    assert.match(
      validateFeedbackAttachment({
        name: "a.mp4",
        mimeType: "video/mp4",
        sizeBytes: FEEDBACK_VIDEO_MAX_BYTES + 1,
      }) ?? "",
      /50 MB per i video/,
    );
  });

  it("rifiuta formati non supportati e accetta peso sconosciuto", () => {
    assert.match(
      validateFeedbackAttachment({ name: "x.pdf", mimeType: "application/pdf", sizeBytes: 10 }) ??
        "",
      /formato non supportato/,
    );
    assert.equal(
      validateFeedbackAttachment({ name: "a.jpg", mimeType: "image/jpeg", sizeBytes: null }),
      null,
    );
  });
});

describe("validateFeedbackDraft", () => {
  it("richiede un testo abbastanza lungo (spazi esclusi)", () => {
    assert.match(validateFeedbackDraft({ message: "  non va  ", attachments: [] }) ?? "", /almeno 10/);
    assert.equal(validateFeedbackDraft({ message, attachments: [] }), null);
  });

  it("limita il numero di allegati", () => {
    const file = { name: "a.png", mimeType: "image/png", sizeBytes: 10 };
    const files = Array.from({ length: FEEDBACK_MAX_ATTACHMENTS + 1 }, () => file);
    assert.match(validateFeedbackDraft({ message, attachments: files }) ?? "", /al massimo 3/);
  });

  it("segnala il primo allegato non valido", () => {
    const problem = validateFeedbackDraft({
      message,
      attachments: [{ name: "x.zip", mimeType: "application/zip", sizeBytes: 5 }],
    });
    assert.match(problem ?? "", /x\.zip/);
  });
});
