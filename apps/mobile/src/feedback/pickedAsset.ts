/**
 * Dal file scelto nella galleria (expo-image-picker) alla forma usata
 * dall'invio. Su Android `mimeType` può mancare: si ricava da `type`
 * (image/video) e dall'estensione, mai "inventando" un formato non supportato.
 */
import type { FeedbackAttachmentDraft } from "@fantappero/contracts";

export type PickedAssetLike = {
  uri: string;
  fileName?: string | null;
  mimeType?: string | null;
  /** "image" | "video" | "livePhoto" | "pairedVideo" */
  type?: string | null;
  fileSize?: number | null;
};

const BY_EXTENSION: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  gif: "image/gif",
  mp4: "video/mp4",
  m4v: "video/mp4",
  mov: "video/quicktime",
  webm: "video/webm",
};

function extensionOf(value: string): string {
  const clean = value.split(/[?#]/)[0] ?? value;
  const dot = clean.lastIndexOf(".");
  return dot >= 0 ? clean.slice(dot + 1).toLowerCase() : "";
}

export function resolveAssetMimeType(asset: PickedAssetLike): string {
  const declared = (asset.mimeType ?? "").toLowerCase();
  if (declared.startsWith("image/") || declared.startsWith("video/")) {
    return declared;
  }
  const fromExtension = BY_EXTENSION[extensionOf(asset.fileName ?? asset.uri)];
  if (fromExtension) {
    return fromExtension;
  }
  return asset.type === "video" ? "video/mp4" : "image/jpeg";
}

export function resolveAssetName(asset: PickedAssetLike, index: number): string {
  const named = asset.fileName?.trim();
  if (named) {
    return named;
  }
  const last = asset.uri.split("/").pop()?.split(/[?#]/)[0];
  if (last) {
    return last;
  }
  return `allegato-${index + 1}`;
}

export type PickedAttachment = FeedbackAttachmentDraft & { uri: string };

export function toPickedAttachment(asset: PickedAssetLike, index: number): PickedAttachment {
  return {
    uri: asset.uri,
    name: resolveAssetName(asset, index),
    mimeType: resolveAssetMimeType(asset),
    sizeBytes: asset.fileSize ?? null,
  };
}
