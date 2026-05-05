export default function ErrorsPage() {
  return (
    <div>
      <div className="page-head">
        <h1>Errori</h1>
      </div>
      <div className="panel">
        <p>Nessun endpoint backend aggregato per error tracking disponibile.</p>
        <ul>
          <li>Ordini con errori parser: non esiste lista dedicata persistita.</li>
          <li>Nested incoerenti: oggi emergono su endpoint di modifica/packing, non in lista centralizzata.</li>
          <li>Documenti non generati/export falliti: non esiste log storico API.</li>
        </ul>
      </div>
    </div>
  );
}
