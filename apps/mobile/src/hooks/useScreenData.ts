import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useRef, useState } from "react";

type LoadOptions = {
  /** Se true non mostra lo spinner a pagina intera (focus / pull). */
  silent?: boolean;
};

/**
 * Carica dati al focus della schermata e supporta pull-to-refresh.
 * Evita doppio fetch se focus e mount coincidono in rapida sequenza.
 */
export function useScreenData<T extends LoadOptions | undefined = LoadOptions | undefined>(
  load: (options?: T) => Promise<void>,
) {
  const [refreshing, setRefreshing] = useState(false);
  const loadRef = useRef(load);
  loadRef.current = load;

  useFocusEffect(
    useCallback(() => {
      void loadRef.current({ silent: true } as T);
    }, []),
  );

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadRef.current({ silent: true } as T);
    } finally {
      setRefreshing(false);
    }
  }, []);

  return { refreshing, onRefresh };
}
