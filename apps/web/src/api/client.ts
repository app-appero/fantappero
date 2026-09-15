import { createApiClient, ApiError, getApiErrorMessage } from "@fantappero/api-client";
import { getWebEnv, resolveApiBaseUrl, WebEnvError } from "../config/env";

export { ApiError, getApiErrorMessage };

type UploadOptions = {
  accessToken: string;
  file: File;
  fieldName?: string;
};

function resolveBaseUrl(): string {
  try {
    return resolveApiBaseUrl(getWebEnv().viteApiBaseUrl);
  } catch (error) {
    if (error instanceof WebEnvError) {
      throw new ApiError("Servizio non disponibile. Riprova tra poco.", 0, "missing_api_base_url");
    }
    throw error;
  }
}

const client = createApiClient<File>({
  resolveBaseUrl,
  buildUploadValue: (file) => file,
  defaultErrorMessage: () => "Si è verificato un errore.",
});

export const apiRequest = client.apiRequest;

export function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  return client.apiUpload<T>(path, options);
}
