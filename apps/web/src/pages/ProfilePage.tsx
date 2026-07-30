import { Breadcrumb, PageContainer, UiStatePanel } from "@fantappero/ui";

/** Profilo utente — wireframe minimo in attesa di EP02-03. */
export function ProfilePage() {
  return (
    <PageContainer title="Profilo" header={<Breadcrumb items={[{ label: "Profilo" }]} />}>
      <UiStatePanel
        state="success"
        title="Account attivo"
        message="Preferenze e sicurezza saranno collegati all'autenticazione EP02-03."
        testId="profile-success"
      />
    </PageContainer>
  );
}

export function NotFoundPage() {
  return (
    <PageContainer title="Pagina non trovata">
      <UiStatePanel
        state="error"
        title="404"
        message="La pagina richiesta non esiste o è stata spostata."
        testId="not-found"
      />
    </PageContainer>
  );
}
