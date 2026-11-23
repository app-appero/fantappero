import { Breadcrumb, PageContainer } from "@fantappero/ui";
import { AdminAppVersionPanel } from "./AdminAppVersionPanel";

/**
 * «Versione app» (release 1.4, canvas «Pannello operatore»): voce di menù a sé, dopo
 * «Segnalazioni». Dentro lo stesso modulo che prima stava in fondo alla prima pagina del
 * pannello: versione, versionCode, link e messaggio, con lo stesso comportamento.
 */
export function AdminAppVersionPage() {
  return (
    <PageContainer
      title="Versione app"
      header={
        <Breadcrumb items={[{ label: "Operazioni", href: "/admin" }, { label: "Versione app" }]} />
      }
    >
      <div className="fa-admin-appversion-page" data-testid="admin-appversion-page">
        <AdminAppVersionPanel hideTitle />
      </div>
    </PageContainer>
  );
}
