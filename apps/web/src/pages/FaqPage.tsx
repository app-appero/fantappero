import {
  FAQ_GROUPS,
  FAQ_INTRO,
  FAQ_QUESTION_PARAM,
  FAQ_TITLE,
  findFaqItem,
  toggleFaqItem,
} from "@fantappero/contracts";
import { Breadcrumb, PageContainer } from "@fantappero/ui";
import { useEffect, useState } from "react";

import { useSearchParams } from "../router/simpleRouter";

/**
 * «Domande frequenti» (release 1.4, canvas approvato da Rosario il 22/11): si legge solo la
 * domanda, un tocco apre la risposta. Il testo è in `@fantappero/contracts` (lo stesso
 * dell'app). Link diretto a una domanda: `/domande-frequenti?domanda=<id>`.
 */
export function FaqPage() {
  const [params] = useSearchParams();
  const linkedId = findFaqItem(params.get(FAQ_QUESTION_PARAM))?.id ?? null;
  const [openIds, setOpenIds] = useState<string[]>(() => (linkedId ? [linkedId] : []));

  useEffect(() => {
    if (!linkedId) {
      return;
    }
    setOpenIds((current) => (current.includes(linkedId) ? current : [...current, linkedId]));
    document.getElementById(`faq-${linkedId}`)?.scrollIntoView?.({ block: "start" });
  }, [linkedId]);

  return (
    <PageContainer
      title={FAQ_TITLE}
      header={<Breadcrumb items={[{ label: "Aiuto" }]} />}
      className="fa-faq"
      data-testid="faq-page"
    >
      <p className="fa-faq__intro">{FAQ_INTRO}</p>
      {FAQ_GROUPS.map((group) => (
        <section
          key={group.id}
          className="fa-faq__group"
          aria-labelledby={`faq-group-${group.id}`}
          data-testid={`faq-group-${group.id}`}
        >
          <h2 id={`faq-group-${group.id}`} className="fa-faq__group-title">
            {group.title}
          </h2>
          <ul className="fa-faq__list">
            {group.items.map((item) => {
              const open = openIds.includes(item.id);
              return (
                <li
                  key={item.id}
                  id={`faq-${item.id}`}
                  className={open ? "fa-faq__item fa-faq__item--open" : "fa-faq__item"}
                  data-testid={`faq-item-${item.id}`}
                >
                  <h3 className="fa-faq__question">
                    <button
                      type="button"
                      id={`faq-q-${item.id}`}
                      className="fa-faq__toggle"
                      aria-expanded={open}
                      aria-controls={`faq-a-${item.id}`}
                      onClick={() => setOpenIds((current) => toggleFaqItem(current, item.id))}
                      data-testid={`faq-toggle-${item.id}`}
                    >
                      <span className="fa-faq__question-text">{item.question}</span>
                      <span className="fa-faq__sign" aria-hidden="true">
                        {open ? "−" : "+"}
                      </span>
                    </button>
                  </h3>
                  <div
                    id={`faq-a-${item.id}`}
                    className="fa-faq__answer"
                    hidden={!open}
                    data-testid={`faq-answer-${item.id}`}
                  >
                    {item.answer.map((paragraph) => (
                      <p key={paragraph}>{paragraph}</p>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </PageContainer>
  );
}
