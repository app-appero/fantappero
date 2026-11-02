import type {
  FeedbackAdminList,
  FeedbackAdminReport,
  FeedbackCategory,
  FeedbackReportSummary,
  FeedbackStatus,
  FeedbackUpdate,
} from "@fantappero/contracts";
import { Platform } from "react-native";
import { apiRequest, apiUploadForm } from "./client";

export type FeedbackUploadFile = { uri: string; name: string; type?: string };

export type SendFeedbackInput = {
  message: string;
  category: FeedbackCategory;
  /** Schermata da cui parte la segnalazione. */
  pageContext?: string;
  appVersion?: string;
  files: readonly FeedbackUploadFile[];
};

export function sendFeedback(
  accessToken: string,
  input: SendFeedbackInput,
): Promise<FeedbackReportSummary> {
  return apiUploadForm<FeedbackReportSummary>("/feedback", {
    accessToken,
    fields: {
      message: input.message.trim(),
      category: input.category,
      pageContext: input.pageContext,
      platform: Platform.OS === "ios" ? "ios" : "android",
      appVersion: input.appVersion,
    },
    files: input.files,
  });
}

export function fetchMyFeedback(accessToken: string): Promise<FeedbackReportSummary[]> {
  return apiRequest<FeedbackReportSummary[]>("/feedback/me", { accessToken });
}

export function fetchAdminFeedback(
  accessToken: string,
  options: { status?: FeedbackStatus; page?: number } = {},
): Promise<FeedbackAdminList> {
  const params = new URLSearchParams();
  if (options.status) {
    params.set("status", options.status);
  }
  if (options.page && options.page > 1) {
    params.set("page", String(options.page));
  }
  const query = params.toString();
  return apiRequest<FeedbackAdminList>(`/admin/feedback${query ? `?${query}` : ""}`, {
    accessToken,
  });
}

export function updateAdminFeedback(
  accessToken: string,
  reportId: string,
  body: FeedbackUpdate,
): Promise<FeedbackAdminReport> {
  return apiRequest<FeedbackAdminReport>(`/admin/feedback/${reportId}`, {
    accessToken,
    method: "PATCH",
    body,
  });
}

export function deleteAdminFeedback(
  accessToken: string,
  reportId: string,
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/admin/feedback/${reportId}`, {
    accessToken,
    method: "DELETE",
  });
}
