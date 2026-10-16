import type {
  PolicyConsentRequest,
  UpdateProfileRequest,
  UserProfile,
} from "@fantappero/contracts";
import { File, UploadType } from "expo-file-system";
import { ApiError, apiRequest } from "./client";
import { loadMobileEnv, MobileEnvError } from "../config/env";

/** Stesso tetto di `AVATAR_MAX_BYTES` (5 MiB). */
export const AVATAR_MAX_BYTES = 5 * 1024 * 1024;

export function fetchProfile(accessToken: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me", { accessToken });
}

export function updateProfile(
  accessToken: string,
  body: UpdateProfileRequest,
): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me", {
    method: "PATCH",
    body,
    accessToken,
  });
}

export function updateInviteAvailability(
  accessToken: string,
  availableForInvites: boolean,
): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/disponibilita-inviti", {
    method: "PATCH",
    body: { availableForInvites },
    accessToken,
  });
}

function avatarMime(type: string | undefined, name: string): string {
  const normalized = (type ?? "").toLowerCase();
  if (normalized === "image/jpg" || normalized === "image/jpeg") {
    return "image/jpeg";
  }
  if (normalized === "image/png" || normalized === "image/webp") {
    return normalized;
  }
  const lowerName = name.toLowerCase();
  if (lowerName.endsWith(".png")) {
    return "image/png";
  }
  if (lowerName.endsWith(".webp")) {
    return "image/webp";
  }
  return "image/jpeg";
}

function messageFromUploadBody(body: string, status: number): string {
  try {
    const payload = JSON.parse(body) as { message?: string; detail?: string };
    if (typeof payload.message === "string" && payload.message.trim()) {
      return payload.message;
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // Corpo non JSON: il chiamante usa il messaggio di fallback.
  }
  if (status === 413) {
    return "L'immagine supera la dimensione massima consentita (5 MB).";
  }
  return "Caricamento avatar non riuscito.";
}

export async function uploadAvatar(
  accessToken: string,
  file: { uri: string; name: string; type?: string },
): Promise<UserProfile> {
  let baseUrl: string;
  try {
    baseUrl = loadMobileEnv().expoPublicApiBaseUrl;
  } catch (error) {
    if (error instanceof MobileEnvError) {
      throw new ApiError("Servizio non disponibile. Riprova tra poco.", 0, "missing_api_base_url");
    }
    throw error;
  }

  const local = new File(file.uri);
  if (local.exists && local.size > AVATAR_MAX_BYTES) {
    throw new ApiError(
      "L'immagine supera la dimensione massima consentita (5 MB).",
      400,
      "avatar_too_large",
    );
  }

  let result: { status: number; body: string };
  try {
    result = await local.upload(`${baseUrl}/profile/me/avatar`, {
      httpMethod: "POST",
      uploadType: UploadType.MULTIPART,
      fieldName: "file",
      mimeType: avatarMime(file.type, file.name),
      sessionType: "foreground",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
    });
  } catch {
    throw new ApiError("Connessione non disponibile. Riprova tra poco.", 0, "network_error");
  }

  if (result.status < 200 || result.status >= 300) {
    throw new ApiError(messageFromUploadBody(result.body, result.status), result.status, "avatar_upload_failed");
  }
  try {
    return JSON.parse(result.body) as UserProfile;
  } catch {
    throw new ApiError("Risposta non valida. Riprova tra poco.", result.status, "invalid_response");
  }
}

export function removeAvatar(accessToken: string): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me/avatar", {
    method: "DELETE",
    accessToken,
  });
}

export function recordPolicyConsent(
  accessToken: string,
  body: PolicyConsentRequest,
): Promise<UserProfile> {
  return apiRequest<UserProfile>("/profile/me/policy-consent", {
    body,
    accessToken,
  });
}
