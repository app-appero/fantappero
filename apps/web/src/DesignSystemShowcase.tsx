import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  Input,
  Select,
  Skeleton,
  Tab,
  TabList,
  TabPanel,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Tabs,
} from "@fantappero/ui";

/** Anteprima non-produttiva dei componenti EPUI-02 (copy demo in italiano). */
export function DesignSystemShowcase() {
  return (
    <section className="fa-ds-showcase" aria-label="Anteprima design system">
      <div className="fa-ds-showcase__section">
        <h2 className="fa-ds-showcase__heading">Pulsanti</h2>
        <div className="fa-ds-showcase__row">
          <Button variant="primary">Primario</Button>
          <Button variant="secondary">Secondario</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Pericolo</Button>
          <Button loading>Caricamento</Button>
          <Button disabled>Disabilitato</Button>
        </div>
      </div>

      <div className="fa-ds-showcase__section">
        <h2 className="fa-ds-showcase__heading">Campi</h2>
        <Card>
          <CardHeader title="Form demo" />
          <CardBody className="fa-stack">
            <Input label="Nome lega" hint="Visibile ai partecipanti" placeholder="Es. Lega amici" />
            <Select
              label="Formato"
              options={[
                { value: "h2h", label: "Scontri diretti" },
                { value: "total", label: "Totale punti" },
              ]}
              placeholder="Seleziona formato"
            />
            <Input label="Email admin" error="Indirizzo non valido" defaultValue="demo" />
          </CardBody>
        </Card>
      </div>

      <div className="fa-ds-showcase__section">
        <h2 className="fa-ds-showcase__heading">Badge e tab</h2>
        <div className="fa-ds-showcase__row">
          <Badge>Neutro</Badge>
          <Badge variant="accent">Accent</Badge>
          <Badge variant="success">Successo</Badge>
          <Badge variant="warning">Attenzione</Badge>
          <Badge variant="danger">Errore</Badge>
        </div>
        <Tabs defaultValue="rosa" aria-label="Sezioni lega demo">
          <TabList>
            <Tab value="rosa">Rosa</Tab>
            <Tab value="mercato">Mercato</Tab>
            <Tab value="classifica">Classifica</Tab>
          </TabList>
          <TabPanel value="rosa">Contenuto tab rosa (placeholder).</TabPanel>
          <TabPanel value="mercato">Contenuto tab mercato (placeholder).</TabPanel>
          <TabPanel value="classifica">Contenuto tab classifica (placeholder).</TabPanel>
        </Tabs>
      </div>

      <div className="fa-ds-showcase__section">
        <h2 className="fa-ds-showcase__heading">Tabella compatta</h2>
        <Table compact>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Giocatore</TableHeaderCell>
              <TableHeaderCell>Ruolo</TableHeaderCell>
              <TableHeaderCell>Valore</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell>Demo A</TableCell>
              <TableCell>
                <Badge variant="accent">C</Badge>
              </TableCell>
              <TableCell>12</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Demo B</TableCell>
              <TableCell>
                <Badge variant="neutral">D</Badge>
              </TableCell>
              <TableCell>8</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <div className="fa-ds-showcase__section">
        <h2 className="fa-ds-showcase__heading">Skeleton e stato vuoto</h2>
        <Skeleton variant="title" />
        <Skeleton variant="text" />
        <EmptyState
          title="Nessun dato"
          description="Anteprima del componente EmptyState senza logica di dominio."
          actions={<Button variant="secondary">Azione demo</Button>}
        />
      </div>
    </section>
  );
}
