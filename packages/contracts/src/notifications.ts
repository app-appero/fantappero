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

/** Piattaforme supportate per la registrazione del token push (EP09-05). */
export type PushDevicePlatform = "ios" | "android";

export interface RegisterPushDeviceRequest {
  token: string;
  platform: PushDevicePlatform;
}

export interface PushDeviceResponse {
  id: string;
  platform: PushDevicePlatform;
}

/** Tipo di comunicazione inviata dagli operatori (sezione Operatori → Notifiche). */
export type BroadcastKind = "test" | "avviso" | "novita" | "manutenzione";

export type BroadcastStatus = "sent" | "scheduled" | "test";

export interface BroadcastAudience {
  mode: "all" | "leagues" | "users";
  leagueIds?: string[];
  userIds?: string[];
  /** Con mode "all" o "leagues": utenti da escludere (selezione "tutti tranne"). */
  excludeUserIds?: string[];
}

export interface CreateBroadcastRequest {
  kind: BroadcastKind;
  title: string;
  body: string;
  category: NotificationCategory;
  deepLink?: string | null;
  channels: { inApp: boolean; push: boolean; email: boolean };
  audience: BroadcastAudience;
  scheduledAt?: string | null;
}

export interface CreateBroadcastResponse {
  id: string;
  status: "sent" | "scheduled";
  recipientCount: number;
  pushCount: number;
}

export interface BroadcastItem {
  id: string;
  kind: BroadcastKind;
  title: string;
  audienceLabel: string;
  recipientCount: number;
  deliveredCount: number;
  readCount: number;
  status: BroadcastStatus;
  sentAt: string | null;
  scheduledAt: string | null;
}

export interface BroadcastList {
  items: BroadcastItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface NotificationRecipient {
  userId: string;
  displayName: string;
  email: string;
  leagues: { id: string; name: string }[];
  pushEnabled: boolean;
  isOperator: boolean;
}

export interface NotificationRecipientList {
  items: NotificationRecipient[];
  total: number;
  page: number;
  pageSize: number;
  counts: { all: number; push: number; noPush: number; operators: number };
}

export interface ListRecipientsFilters {
  search?: string;
  leagueId?: string;
  pushOnly?: boolean;
  noPush?: boolean;
  operatorsOnly?: boolean;
  page?: number;
  pageSize?: number;
}

export interface TestSampleItem {
  key: string;
  title: string;
  body: string;
  category: NotificationCategory;
}

export interface TestSampleList {
  items: TestSampleItem[];
}

export interface SendTestSamplesRequest {
  sampleKeys?: string[];
  userIds?: string[];
}

export const BROADCAST_KIND_OPTIONS: ReadonlyArray<{
  value: BroadcastKind;
  label: string;
  description: string;
}> = [
  { value: "test", label: "Test", description: "Solo per verificare, arriva a te o a chi scegli" },
  { value: "avviso", label: "Avviso", description: "Comunicazione importante a tutti o ad un gruppo" },
  { value: "novita", label: "Novità", description: "Nuove funzioni e aggiornamenti dell’app" },
  { value: "manutenzione", label: "Manutenzione", description: "Interruzioni programmate del servizio" },
];

export const BROADCAST_DESTINATIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "/", label: "Home della lega" },
  { value: "/turni", label: "Turni" },
  { value: "/formazione", label: "Formazione" },
  { value: "/mercato", label: "Mercato" },
  { value: "/classifica", label: "Classifica" },
  { value: "/inviti", label: "Inviti" },
  { value: "/profilo", label: "Profilo" },
];

export const BROADCAST_CATEGORY_OPTIONS: ReadonlyArray<{
  value: NotificationCategory;
  label: string;
}> = [
  { value: "sistema", label: "Sistema" },
  { value: "formazione", label: "Formazione" },
  { value: "mercato", label: "Mercato" },
  { value: "risultati", label: "Risultati" },
];
