import {
  Button,
  EmptyState,
  Skeleton,
  UiStatePanel,
  type UiState,
} from "@fantappero/ui";
import type { ReactNode } from "react";
import type { WireframeScreenMeta } from "./catalog";

export type RenderWireframeBodyOptions = {
  screen: WireframeScreenMeta;
  state: UiState;
  successContent: ReactNode;
  emptyActions?: ReactNode;
  errorActions?: ReactNode;
};

export function renderWireframeBody({
  screen,
  state,
  successContent,
  emptyActions,
  errorActions,
}: RenderWireframeBodyOptions): ReactNode {
  const testId = `wireframe-${screen.id}-${state}`;

  if (state === "loading") {
    return (
      <div data-testid={testId}>
        <UiStatePanel
          state="loading"
          title={screen.loading.title}
          message={screen.loading.message}
          testId={`${testId}-panel`}
        />
        <div className="fa-wireframe-loading-skeletons" aria-hidden="true">
          <Skeleton variant="title" width="60%" />
          <Skeleton variant="text" width="100%" />
          <Skeleton variant="block" height={120} />
        </div>
      </div>
    );
  }

  if (state === "empty") {
    const actions =
      emptyActions ??
      (screen.empty.ctaLabel ? (
        <Button variant="primary">{screen.empty.ctaLabel}</Button>
      ) : undefined);

    return (
      <EmptyState
        title={screen.empty.title}
        description={screen.empty.description}
        actions={actions}
        testId={testId}
      />
    );
  }

  if (state === "error") {
    return (
      <div data-testid={testId}>
        <UiStatePanel
          state="error"
          title={screen.error.title}
          message={screen.error.message}
          testId={`${testId}-panel`}
        />
        {errorActions ??
          (screen.error.retryLabel ? (
            <div className="fa-wireframe-error-actions">
              <Button variant="secondary">{screen.error.retryLabel}</Button>
            </div>
          ) : null)}
      </div>
    );
  }

  if (state === "forbidden") {
    return (
      <UiStatePanel
        state="forbidden"
        title={screen.forbidden.title}
        message={screen.forbidden.message}
        testId={testId}
      />
    );
  }

  return <div data-testid={testId}>{successContent}</div>;
}
