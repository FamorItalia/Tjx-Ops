# Manuale d'Uso - TJX Ops Hub

Versione: 1.0  
Ambito: uso operativo interno ufficio

## 1) Accesso al portale

1. Aprire il browser.
2. Inserire l'URL del portale (esempio interno): `http://<IP_PC_SERVER>:3001/login`
3. Inserire utente e password.
4. Una volta autenticati, la sessione resta attiva fino a uscita manuale (`Esci`).

## 2) Menu principale

- Dashboard
- Archivio Ordini (ordini segnati spediti)
- Fornitori
- Prodotti
- Insegne
- Errori
- Nuovo Import
- Utenti (solo profili abilitati)

## 3) Flusso operativo standard (ordine cliente -> documenti)

1. Andare su `Nuovo Import`.
2. Caricare PDF ordine cliente.
3. Verificare preview parsing (PO, customer, date, righe, warning).
4. Confermare salvataggio ordine.
5. Aprire l'ordine da `Dashboard`.
6. Verificare/aggiornare:
   - righe ordine
   - nested (automatico o manuale)
   - quantità operative
   - dati DC (fattura/data/pesi/volumi/pallet se override)
7. Generare documenti DC (Packing List, DLE, Sfarinati, P2 in base ai flag prodotti).
8. Scaricare singoli documenti o `Scarica tutto PDF/Excel`.
9. Quando completato, usare `Segna spedito`.

## 4) Dashboard

Funzioni principali:
- Elenco ordini da spedire
- Filtri rapidi
- Apertura dettaglio ordine (`Apri`)
- Azioni riga:
  - `Segna spedito`
  - `Elimina` (con conferma)
- Notifiche giacenze (visibili solo se presenti alert attivi)

## 5) Nuovo Import

Funzioni:
- Upload PDF reale
- Test parser
- Salvataggio ordine

Controlli da fare sempre prima di salvare:
- PO corretto
- Customer corretto
- Date ship/cancel corrette
- Numero righe prodotto corretto
- Warning parser da valutare

## 6) Dettaglio Ordine (pagina operativa centrale)

### 6.1 Header ordine

Mostra:
- PO
- Customer
- Fornitore
- Start Ship Date
- Cancel Date
- Stato (Programmato / Pronto al ritiro / In ritardo)

Azioni:
- Aggiorna
- Segna spedito
- Elimina ordine

### 6.2 Ordine ricevuto

Tabella con:
- Vendor Style
- Master Carton
- Descrizione
- Nest Code
- Quantità per DC
- Totali PCS e CS
- Valori economici lato vendita (se presenti)

Azioni:
- `Salva modifiche`
- `Nest manuali` (attiva gestione manuale nest)
- `Ripristina ordine originale`
- `Aggiusta qty ordine` (normalizza divisibilità pack)

### 6.3 Ordine da inviare al fornitore

Tabella operativa con:
- Stessa struttura righe/DC
- Totali PCS/CS
- Valori economici lato costo (se presenti)

Azioni:
- `Applica aumento automatico +2%` (per DC, senza superare +2%)
- `Ripristina = ordine cliente`
- `Salva modifiche`
- Generazione ordine fornitore (PDF/Excel)

### 6.4 Riepilogo per DC

Per ogni DC:
- Pezzi
- Cartoni
- Volume
- Peso lordo
- Peso netto
- Pallets
- Numero fattura
- Data fattura

Azioni:
- `Salva DC`
- Genera documento DC (tipo + formato)
- `Genera`

Azioni globali:
- Data fattura comune + applicazione a tutti i DC
- Numero fattura progressivo (autocompilazione incrementale)
- Scarica tutto PDF
- Scarica tutto Excel
- Ripristino valori logistici calcolati

### 6.5 Documenti

I documenti sono gestiti per:
- Livello PO
- Livello PO/DC

Azioni:
- Apri
- Scarica

## 7) Documenti export

## 7.1 Packing List

- Una packing list per ogni DC.
- Dati da ordine + anagrafiche prodotti/DC/fornitori.
- Include footer ISPM15.

## 7.2 DLE

- Generazione per DC.
- Campi dinamici: numero fattura, data fattura, data odierna.

## 7.3 Sfarinati

- Disponibile solo se almeno un prodotto ordine ha flag `HAS_SFARINATI = TRUE`.
- Generazione per DC.

## 7.4 P2

- Disponibile solo se almeno un prodotto ordine ha flag `HAS_P2 = TRUE`.
- Generazione per DC.

## 8) Fornitori

Funzioni:
- Elenco fornitori
- `Aggiungi fornitore`
- Dettaglio fornitore
- Modifica anagrafica
- Upload documenti/certificazioni
- Rinomina documento
- Download documento
- Elimina documento (con conferma)
- Export Excel / Import Excel
- Template testo email modificabile

## 9) Prodotti

Funzioni:
- Elenco prodotti con ricerca/filtri
- `Aggiungi prodotto`
- Dettaglio prodotto
- Modifica dati logistici
- Gestione prezzi separata da giacenze
- Documenti allegati (upload / rename / download / elimina con conferma)
- Export Excel / Import Excel

## 10) Giacenze

Concetti:
- Gacenza prodotto
- Giacenza packaging
- Coefficiente di utilizzo

Comportamento:
- Le giacenze si aggiornano con i consumi ordine.
- Alert in dashboard quando sotto soglia.
- Storico movimentazioni consultabile dal blocco dedicato.

## 11) Insegne

Pagina `Insegne`:
- 7 insegne con logo cliccabile
- Recap ultimi 12 mesi:
  - Totali lavorati
  - Spediti
  - Da spedire
  - Fatturato annuo mobile (vendita)

Pagina singola insegna:
- Ordini ultimi 12 mesi
- Filtro mese/anno
- Riga per PO con totali principali

## 12) Utenti e permessi

Funzioni:
- Creazione utenti
- Assegnazione livello accesso
- Login persistente
- Logout manuale (`Esci`)
- Tracciamento modifiche via audit log backend

## 13) Errori comuni e soluzione rapida

1. `Login fallito`
- Verificare backend attivo su porta 8000.
- Verificare credenziali utente.

2. `Documento non generato`
- Controllare che livello (PO/DC) e tipo documento siano coerenti.
- Verificare dati obbligatori DC (es. fattura/data se richiesti).

3. `Nessun documento DC disponibile`
- Verificare flag prodotto (`HAS_SFARINATI`, `HAS_P2`).
- Verificare che l'ordine abbia righe prodotto collegate a anagrafica.

4. `Ordine duplicato import`
- Il sistema deve bloccare PO già importato; se compare doppio, usare eliminazione con conferma sull'ordine errato.

## 14) Procedura giornaliera consigliata

1. Aprire Dashboard.
2. Controllare notifiche giacenze.
3. Importare nuovi ordini.
4. Completare dettaglio ordine e dati DC.
5. Generare e scaricare documenti.
6. Segnare spediti gli ordini chiusi.

---

## Allegato A - Screenshot da inserire (mirati)

Per un manuale utile, servono questi screenshot contestualizzati:

1. Login: pagina login + campi.
2. Dashboard: tabella ordini + azioni riga.
3. Nuovo Import: upload + preview parser + warning.
4. Dettaglio Ordine (header + ordine ricevuto).
5. Dettaglio Ordine (ordine fornitore + pulsanti +2% e ripristino).
6. Riepilogo DC: campi fattura/data + selezione tipo documento + genera.
7. Documenti generati: sezione con Apri/Scarica.
8. Fornitori: dettaglio fornitore + tab documenti.
9. Prodotti: dettaglio prodotto + blocco logistica/prezzi/giacenze.
10. Insegne: vista loghi + pagina singola insegna filtrata.
11. Notifiche giacenze: caso reale sotto soglia.
12. Utenti: pagina utenti con ruoli/livelli.

Nomenclatura file consigliata:
- `01_login.png`
- `02_dashboard.png`
- `03_import_preview.png`
- `04_ordine_header_ricevuto.png`
- `05_ordine_fornitore.png`
- `06_riepilogo_dc.png`
- `07_documenti.png`
- `08_fornitore_dettaglio.png`
- `09_prodotto_dettaglio.png`
- `10_insegne.png`
- `11_alert_giacenze.png`
- `12_utenti.png`

