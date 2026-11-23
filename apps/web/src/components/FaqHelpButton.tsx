import {
  FAQ_HELP_ALL_LABEL,
  FAQ_HELP_CLOSE_LABEL,
  faqHelpItem,
  faqHelpLabel,
  faqQuestionHref,
  type FaqHelpId,
} from "@fantappero/contracts";
import { Button, Modal } from "@fantappero/ui";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Link } from "../router/simpleRouter";

export type FaqHelpButtonProps = {
  /** La domanda da aprire: uno degli id di `FAQ_HELP`. */
  faqId: FaqHelpId;
  className?: string;
  "data-testid"?: string;
};

/**
 * Il piccolo «?» accanto a una scritta (1.4, canvas approvato da Rosario il 22/11): un tocco
 * apre la risposta della domanda frequente, dal basso sul telefono e come finestra sul
 * computer, con il link «Tutte le domande frequenti» alla pagina con quella domanda aperta.
 *
 * Il testo è quello di `@fantappero/contracts` (lo stesso dell'app). Il nome accessibile è la
 * domanda senza virgolette («Perché un turno è saltato?»); il cerchio si vede di 22px ma l'area
 * di tocco è di 44px. La finestra va in fondo a `<body>`: il «?» sta anche dentro un `<p>`,
 * dove una finestra non può stare, e così copre anche header e barre della pagina.
 */
export function FaqHelpButton({ faqId, className, "data-testid": testId }: FaqHelpButtonProps) {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const item = faqHelpItem(faqId);
  const baseTestId = testId ?? `faq-help-${faqId}`;
  const close = () => setOpen(false);

  // Chiusa la risposta, il fuoco torna sul «?»: Safari non dà il fuoco a un pulsante toccato,
  // quindi quello che la finestra ricorda da sola sarebbe il corpo della pagina.
  useEffect(() => {
    if (wasOpen.current && !open) {
      buttonRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className={className ? `fa-faq-help ${className}` : "fa-faq-help"}
        aria-label={faqHelpLabel(item)}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        data-testid={baseTestId}
      >
        <span className="fa-faq-help__glyph" aria-hidden="true">
          ?
        </span>
      </button>
      {open && typeof document !== "undefined"
        ? createPortal(
            <Modal
              open
              onClose={close}
              title={item.question}
              className="fa-faq-sheet"
              footer={
                <>
                  <Link
                    to={faqQuestionHref(item.id)}
                    className="fa-faq-sheet__all"
                    onClick={close}
                    data-testid={`${baseTestId}-all`}
                  >
                    {FAQ_HELP_ALL_LABEL}
                    {/* Spazio fisso: nel link (inline-flex) uno spazio normale sparirebbe. */}
                    <span aria-hidden="true">{"\u00a0›"}</span>
                  </Link>
                  <Button type="button" onClick={close} data-testid={`${baseTestId}-close`}>
                    {FAQ_HELP_CLOSE_LABEL}
                  </Button>
                </>
              }
            >
              <div className="fa-faq-sheet__answer" data-testid={`${baseTestId}-answer`}>
                {item.answer.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </Modal>,
            document.body,
          )
        : null}
    </>
  );
}
