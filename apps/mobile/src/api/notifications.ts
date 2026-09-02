import type {
  ListNotificationsFilters,
  MarkAllNotificationsReadResult,
  NotificationItem,
  NotificationList,
  NotificationPreferenceList,
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
