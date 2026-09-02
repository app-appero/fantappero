/** In-app notification center contracts (EP09-01). */

export type NotificationCategory = "sistema" | "formazione" | "mercato" | "risultati";

export interface NotificationItem {
  id: string;
  category: NotificationCategory;
  title: string;
  body: string;
  deepLink: string | null;
  read: boolean;
  readAt: string | null;
  createdAt: string;
}

export interface NotificationList {
  items: NotificationItem[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  unreadCount: number;
}

export interface MarkAllNotificationsReadResult {
  markedCount: number;
}

export interface NotificationPreference {
  category: NotificationCategory;
  inAppEnabled: boolean;
}

export interface NotificationPreferenceList {
  items: NotificationPreference[];
}

export interface UpdateNotificationPreferenceRequest {
  category: NotificationCategory;
  inAppEnabled: boolean;
}

export interface ListNotificationsFilters {
  category?: NotificationCategory;
  unreadOnly?: boolean;
  page?: number;
  pageSize?: number;
}
