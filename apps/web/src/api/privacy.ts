import type {
  AccountDataExport,
  AuthErrorResponse,
  DeleteAccountRequest,
  PrivacyMessageResponse,
} from "@fantappero/contracts";
import { getWebEnv } from "../config/env";
import { ApiError, apiRequest } from "./client";

export function exportAccountData(accessToken: string): Promise<AccountDataExport> {
  return downloadJson<AccountDataExport>("/profile/me/export", accessToken);
}

export function deleteAccount(
  accessToken: string,
  body: DeleteAccountRequest,
): Promise<PrivacyMessageResponse> {
  return apiRequest<PrivacyMessageResponse>("/profile/me/delete", {
    body,
    accessToken,
  });
}

async function downloadJson<T>(path: string, accessToken: string): Promise<T> {
  const { viteApiBaseUrl } = getWebEnv();
  const response = await fetch(`${viteApiBaseUrl}${path}`, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const payload = (await response.json()) as T | AuthErrorResponse;
  if (!response.ok) {
    const errorPayload = payload as AuthErrorResponse;
    throw new ApiError(
      errorPayload.message ?? "Si è verificato un errore.",
      response.status,
      errorPayload.code ?? "unknown_error",
    );
  }
  return payload as T;
}
