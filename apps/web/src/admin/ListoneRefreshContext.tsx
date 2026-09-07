import type { AdminListoneRefreshProgress, AdminListoneRefreshResult } from "@fantappero/contracts";
import { ProgressBar } from "@fantappero/ui";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  fetchActiveAdminListoneRefresh,
  fetchAdminListoneRefreshProgress,
  startAdminListoneRefresh,
} from "../api/admin";
import { useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";

export type ListoneRefreshProgress = {
  percent: number;
  stage: string;
  message: string;
};

export type ListoneRefreshContextValue = {
  refreshing: boolean;
  progress: ListoneRefreshProgress | null;
  seasonYear: number | null;
  startRefresh: (accessToken: string, seasonYear: number) => Promise<AdminListoneRefreshResult>;
};

const ListoneRefreshContext = createContext<ListoneRefreshContextValue | null>(null);

export type ListoneRefreshProviderProps = {
  children: ReactNode;
};

const POLL_INTERVAL_MS = 800;
const AMBIENT_CHECK_INTERVAL_MS = 15_000;

function isActiveStatus(status: string): boolean {
  return status === "queued" || status === "running";
}

async function pollJob(
  accessToken: string,
  jobId: string,
  onUpdate: (progress: AdminListoneRefreshProgress) => void,
): Promise<AdminListoneRefreshResult> {
  for (;;) {
    const progress = await fetchAdminListoneRefreshProgress(accessToken, jobId);
    onUpdate(progress);
    if (progress.status === "completed") {
      if (!progress.result) {
        throw new Error("Aggiornamento completato senza risultato.");
      }
      return progress.result;
    }
    if (progress.status === "failed") {
      throw new Error(progress.message || "Aggiornamento listone non riuscito.");
    }
    await new Promise((resolve) => {
      window.setTimeout(resolve, POLL_INTERVAL_MS);
    });
  }
}

/**
 * Owns the listone-refresh progress at the app root (not page-local state)
 * so the global bar below stays visible across route changes and across
 * every global operator's own session — not just the one who clicked
 * "Aggiorna" — since the refresh itself can take several minutes against a
 * rate-limited provider.
 */
export function ListoneRefreshProvider({ children }: ListoneRefreshProviderProps) {
  const { isDemoMode, can } = useAuth();
  const [refreshing, setRefreshing] = useState(false);
  const [progress, setProgress] = useState<ListoneRefreshProgress | null>(null);
  const [seasonYear, setSeasonYear] = useState<number | null>(null);
  const inFlightRef = useRef<Promise<AdminListoneRefreshResult> | null>(null);

  const watch = useCallback(
    (accessToken: string, jobId: string, year: number | null): Promise<AdminListoneRefreshResult> => {
      setRefreshing(true);
      setSeasonYear(year);
      const promise = pollJob(accessToken, jobId, (next) =>
        setProgress({ percent: next.percent, stage: next.stage, message: next.message }),
      ).finally(() => {
        inFlightRef.current = null;
        setRefreshing(false);
        setProgress(null);
        setSeasonYear(null);
      });
      inFlightRef.current = promise;
      return promise;
    },
    [],
  );

  const startRefresh = useCallback(
    (accessToken: string, year: number): Promise<AdminListoneRefreshResult> => {
      if (inFlightRef.current) {
        return inFlightRef.current;
      }
      setProgress({ percent: 0, stage: "queued", message: "Avvio in corso…" });
      const promise = startAdminListoneRefresh(accessToken, year).then((job) =>
        watch(accessToken, job.jobId, year),
      );
      inFlightRef.current = promise;
      return promise;
    },
    [watch],
  );

  // Ambient watcher: discovers a refresh some OTHER operator already started,
  // so this session's bar shows it too instead of staying blind to it.
  useEffect(() => {
    if (isDemoMode || refreshing || !can(["global:operate"])) {
      return;
    }
    let cancelled = false;
    let timeoutId: number;

    async function tick() {
      const session = loadStoredSession();
      if (session?.accessToken) {
        try {
          const active = await fetchActiveAdminListoneRefresh(session.accessToken);
          if (!cancelled && active && isActiveStatus(active.status)) {
            void watch(session.accessToken, active.jobId, null);
            return;
          }
        } catch {
          // Best-effort ambient check — a transient failure just retries later.
        }
      }
      if (!cancelled) {
        timeoutId = window.setTimeout(tick, AMBIENT_CHECK_INTERVAL_MS);
      }
    }

    void tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [isDemoMode, can, refreshing, watch]);

  return (
    <ListoneRefreshContext.Provider value={{ refreshing, progress, seasonYear, startRefresh }}>
      {refreshing ? (
        <div className="fa-listone-refresh-bar" data-testid="listone-refresh-global-bar">
          <ProgressBar
            percent={progress?.percent ?? 0}
            label={`Listone${seasonYear ? ` ${seasonYear}` : ""}: ${
              progress?.message ?? "Aggiornamento in corso…"
            } (${progress?.percent ?? 0}%)`}
          />
        </div>
      ) : null}
      {children}
    </ListoneRefreshContext.Provider>
  );
}

export function useListoneRefresh(): ListoneRefreshContextValue {
  const context = useContext(ListoneRefreshContext);
  if (!context) {
    throw new Error("useListoneRefresh must be used within ListoneRefreshProvider");
  }
  return context;
}
