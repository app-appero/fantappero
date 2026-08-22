import { createApiClient, ApiError } from "@fantappero/api-client";
import { getWebEnv } from "../config/env";

export { ApiError };

type UploadOptions = {
  accessToken: string;
  file: File;
  fieldName?: string;
};

const client = createApiClient<File>({
  resolveBaseUrl: () => getWebEnv().viteApiBaseUrl,
  buildUploadValue: (file) => file,
  defaultErrorMessage: () => "Si è verificato un errore.",
});

export const apiRequest = client.apiRequest;

export function apiUpload<T>(path: string, options: UploadOptions): Promise<T> {
  return client.apiUpload<T>(path, options);
}
