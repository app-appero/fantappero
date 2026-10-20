import type {
  BroadcastList,
  CreateBroadcastRequest,
  CreateBroadcastResponse,
  ListRecipientsFilters,
  NotificationRecipientList,
  SendTestSamplesRequest,
  SendTestSamplesResult,
  TestSampleList,
  ListNotificationsFilters,
  MarkAllNotificationsReadResult,
  NotificationItem,
  NotificationList,
  NotificationPreferenceList,
  PushDeviceResponse,
  RegisterPushDeviceRequest,
  UpdateNotificationPreferenceRequest,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export function fetchNotifications(
  accessToken: string,
  filters: ListNotificationsFilters = {},
): Promise<NotificationList> {
  const params = new URLSearchParams();
  if (filters.category) {
    params.set("category", filters.category);
  }
  if (filters.unreadOnly) {
    params.set("unreadOnly", "true");
  }
  if (filters.page) {
    params.set("page", String(filters.page));
  }
  if (filters.pageSize) {
    params.set("pageSize", String(filters.pageSize));
  }
  const qs = params.toString();
  return apiRequest<NotificationList>(`/notifications${qs ? `?${qs}` : ""}`, { accessToken });
}

export function markNotificationRead(
  accessToken: string,
  notificationId: string,
): Promise<NotificationItem> {
  return apiRequest<NotificationItem>(`/notifications/${notificationId}/read`, {
    accessToken,
    method: "POST",
  });
}

export function markAllNotificationsRead(
  accessToken: string,
): Promise<MarkAllNotificationsReadResult> {
  return apiRequest<MarkAllNotificationsReadResult>("/notifications/read-all", {
    accessToken,
    method: "POST",
  });
}

export function fetchNotificationPreferences(
  accessToken: string,
): Promise<NotificationPreferenceList> {
  return apiRequest<NotificationPreferenceList>("/notifications/preferences", { accessToken });
}

export function updateNotificationPreference(
  accessToken: string,
  body: UpdateNotificationPreferenceRequest,
): Promise<NotificationPreferenceList> {
  return apiRequest<NotificationPreferenceList>("/notifications/preferences", {
    accessToken,
    method: "PUT",
    body,
  });
}

export function registerPushDevice(
  accessToken: string,
  body: RegisterPushDeviceRequest,
): Promise<PushDeviceResponse> {
  return apiRequest<PushDeviceResponse>("/notifications/push-devices", {
    accessToken,
    method: "POST",
    body,
  });
}

export function unregisterPushDevice(accessToken: string, token: string): Promise<void> {
  return apiRequest<void>(`/notifications/push-devices/${encodeURIComponent(token)}`, {
    accessToken,
    method: "DELETE",
  });
}

/** Operatori: crea una notifica di esempio per ogni tipo (solo per test). */
export function sendTestNotifications(
  accessToken: string,
): Promise<MarkAllNotificationsReadResult> {
  return apiRequest<MarkAllNotificationsReadResult>("/notifications/test-samples", {
    accessToken,
    method: "POST",
  });
}

export function fetchNotificationRecipients(
  accessToken: string,
  filters: ListRecipientsFilters = {},
): Promise<NotificationRecipientList> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.leagueId) params.set("leagueId", filters.leagueId);
  if (filters.pushOnly) params.set("pushOnly", "true");
  if (filters.noPush) params.set("noPush", "true");
  if (filters.operatorsOnly) params.set("operatorsOnly", "true");
  if (filters.page) params.set("page", String(filters.page));
  if (filters.pageSize) params.set("pageSize", String(filters.pageSize));
  const qs = params.toString();
  return apiRequest<NotificationRecipientList>(
    `/admin/notifications/recipients${qs ? `?${qs}` : ""}`,
    { accessToken },
  );
}

export function createBroadcast(
  accessToken: string,
  body: CreateBroadcastRequest,
): Promise<CreateBroadcastResponse> {
  return apiRequest<CreateBroadcastResponse>("/admin/notifications/broadcasts", {
    accessToken,
    method: "POST",
    body,
  });
}

export function fetchBroadcasts(accessToken: string, page = 1): Promise<BroadcastList> {
  return apiRequest<BroadcastList>(`/admin/notifications/broadcasts?page=${page}`, {
    accessToken,
  });
}

export function fetchTestSamples(accessToken: string): Promise<TestSampleList> {
  return apiRequest<TestSampleList>("/admin/notifications/test-samples", { accessToken });
}

export function sendTestSamples(
  accessToken: string,
  body: SendTestSamplesRequest,
): Promise<SendTestSamplesResult> {
  return apiRequest<SendTestSamplesResult>("/admin/notifications/test-samples", {
    accessToken,
    method: "POST",
    body,
  });
}
