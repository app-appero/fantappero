import type { ConfirmCopy } from "@fantappero/contracts";
import { Button, Modal } from "@fantappero/ui";

export type RunConfirmModalProps = {
  /** Titolo, domanda e pulsanti (`@fantappero/contracts`); `null` = finestra chiusa. */
  copy: ConfirmCopy | null;
  onConfirm: () => void;
  onCancel: () => void;
  testId: string;
};

/**
 * «Sei sicuro?» di «Esegui» e «Esegui tutti» nel pannello operatore (1.5). I testi arrivano da
 * `@fantappero/contracts`, gli stessi dell'app; l'elenco delle operazioni va a capo come nel testo.
 */
export function RunConfirmModal({ copy, onConfirm, onCancel, testId }: RunConfirmModalProps) {
  return (
    <Modal
      open={copy !== null}
      onClose={onCancel}
      title={copy?.title ?? ""}
      footer={
        copy ? (
          <>
            <Button type="button" variant="ghost" onClick={onCancel} data-testid={`${testId}-cancel`}>
              {copy.cancelLabel}
            </Button>
            <Button type="button" onClick={onConfirm} data-testid={`${testId}-confirm`}>
              {copy.confirmLabel}
            </Button>
          </>
        ) : null
      }
    >
      {copy ? (
        <p className="fa-run-confirm__text" data-testid={`${testId}-text`}>
          {copy.message}
        </p>
      ) : null}
    </Modal>
  );
}
