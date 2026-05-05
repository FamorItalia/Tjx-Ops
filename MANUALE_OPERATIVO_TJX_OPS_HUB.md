# Manuale Operativo - TJX Ops Hub

Versione: 1.0  
Obiettivo: guida pratica su cosa fare, quando farlo, e cosa succede nel sistema.

## 1) Flusso operativo standard (da ordine cliente a spedizione)

1. Vai su `Nuovo Import`.
2. Carica il PDF ordine cliente.
3. Controlla la preview parsing.
4. Salva l’ordine.
5. Apri l’ordine in Dashboard (`Apri`).
6. Verifica quantità, nested, dati DC.
7. Genera documenti DC / PO.
8. Scarica documenti.
9. Segna ordine come `Spedito`.

## 2) Cosa fanno i pulsanti principali (e quando usarli)

## 2.1 Dashboard

- `Apri`: entra nel dettaglio ordine.
- `Segna spedito`: sposta ordine da “attivi” a “spediti”.
- `Elimina`: cancella ordine (con conferma).

Quando usarli:
- `Segna spedito` solo a processo documentale chiuso.
- `Elimina` solo per import errato o duplicato reale.

## 2.2 Dettaglio ordine - blocco Ordine ricevuto

- `Salva modifiche`: salva modifiche righe (vendor style, nest, quantità ricevute).
- `Nest manuali`: abilita modifica manuale del `Nest Code`.
- `Ripristina ordine originale`: ripristina i valori importati da parser.
- `Aggiusta qty ordine`: corregge quantità non divisibili con la logica pack.

Quando usare `Aggiusta qty ordine`:
- warning tipo “units non divisibili per store_ready/master carton”.
- scenario in cui il cliente manda quantità sporche e serve allinearle.

## 2.3 Dettaglio ordine - blocco Ordine da inviare al fornitore

- `Applica aumento automatico +2%`: applica aumento per DC senza superare il +2%.
- `Ripristina = ordine cliente`: annulla modifiche operative e riallinea al cliente.
- `Salva modifiche`: salva quantità operative manuali.
- `Genera ordine fornitore`: produce documento fornitore.

## 2.4 Riepilogo per DC

- `Salva DC`: salva numero fattura, data fattura e override logistici.
- `Genera`: genera documento selezionato per quel DC.
- `Applica data a tutti i DC`: copia data fattura comune nei singoli DC.
- `Scarica tutto PDF`: genera (se manca) e scarica tutto export PDF ordine.
- `Scarica tutto Excel`: genera (se manca) e scarica tutto export Excel ordine.
- `Ripristino valori calcolati`: annulla override manuali volume/pesi/pallet e ripristina calcolo motore.

## 3) Nested manuale: quando usarlo e logica

Usalo quando il parser non riconosce bene il nest o l’ordine cliente è incoerente.

Regole pratiche:
- stesso gruppo nest = stesso `Master Carton` per tutte le SKU del gruppo.
- se `Master Carton` differisce nello stesso gruppo -> errore bloccante.
- store-ready per SKU viene riconciliato dal master del gruppo (se possibile).
- se quantità DC non divisibili per pack del gruppo -> warning/errore.

Cosa aspettarti:
- badge `Nested riconciliato automaticamente` quando il sistema ha corretto store-ready incoerenti.
- in caso di incongruenza forte, blocco calcoli/documenti finché non correggi.

## 4) Come funziona l’aumento automatico +2%

Regola chiave:
- +2% massimo per singolo DC, mai sul totale ordine globale.

Mono:
- usa pack mono (`master carton`) e prende il massimo numero di cartoni completi entro +2%.

Nested:
- calcolo a livello gruppo nest, non per SKU indipendente.
- tutte le SKU del gruppo devono convergere allo stesso numero cartoni gruppo.

Effetto:
- se il +2% non basta ad aggiungere un cartone completo, quantità resta invariata.

## 5) Generazione documenti: singola e massiva

## 5.1 Generazione singola per DC

Nel riquadro DC:
1. Scegli tipo documento.
2. Scegli formato (PDF/Excel).
3. `Genera`.

Tipi disponibili:
- Packing List: sempre.
- DLE: sempre.
- Sfarinati: solo se almeno un prodotto ha flag `HAS_SFARINATI`.
- P2: solo se almeno un prodotto ha flag `HAS_P2`.

## 5.2 Generazione massiva

- `Scarica tutto PDF` / `Scarica tutto Excel`:
  - genera i documenti export mancanti
  - crea ZIP unico per PO
  - include solo documenti export (no ordine fornitore)

## 6) Numero fattura e data fattura: logica corretta

Campi per DC:
- ogni DC può avere proprio numero fattura e data.

Campo progressivo:
- se compili `xxx/EM/AAAA`, il sistema propone incremento progressivo sui DC successivi.
- resta sempre modificabile manualmente in ogni DC.

Data fattura comune:
- è una scorciatoia di compilazione.
- dopo applicazione, ogni DC resta comunque editabile.

## 7) Override logistici DC (volume, pesi, pallet)

Campi editabili:
- Volume (m³)
- Peso lordo
- Peso netto
- Pallets

Uso:
- se il rilevato reale magazzino differisce dal calcolo automatico.

Importante:
- dopo override, packing list e riepiloghi usano i valori salvati.
- con `Ripristino valori calcolati` torni ai valori del motore.

## 8) Logica giacenze: come funziona davvero

Due livelli:
- giacenza prodotto
- giacenza packaging

Meccanismo:
- ogni ordine consuma pezzi e/o packaging in base ai coefficienti prodotto.
- i consumi finiscono nello storico movimentazioni.

Esempio packaging:
- stock iniziale 10 kg
- coefficiente 0,01 kg/pezzo
- consumo totale 467 pezzi -> 4,67 kg
- stock residuo 5,33 kg

Alert:
- scattano quando il livello attuale scende sotto soglia.
- appaiono in Dashboard (solo alert attivi correnti).

## 9) Import/Export anagrafiche: uso sicuro

Per `Fornitori` e `Prodotti`:
- `Export Excel`: scarica stato anagrafica attuale.
- modifica offline in Excel.
- `Import Excel`: ricarica e rende attive le modifiche.

Buona pratica:
1. esporta sempre prima di cambiare;
2. conserva backup con data;
3. reimporta;
4. verifica su un ordine test.

## 10) Correzione errori frequenti (operativa)

1. Documento DC non disponibile:
- verifica flag prodotto (`HAS_SFARINATI`, `HAS_P2`).

2. Fornitore errato:
- verifica match vendor style -> anagrafica prodotti -> fornitore.

3. Nested incoerente:
- controlla master carton gruppo e divisibilità quantità DC.

4. Totali non tornano:
- verifica se ci sono override manuali DC attivi.

5. Dati cambiati ma non visibili:
- premere `Salva modifiche` / `Salva DC` nel blocco corretto.

## 11) Procedura rapida consigliata per ogni nuovo PO

1. Import PDF.
2. Apri ordine.
3. Controlla warning.
4. Se serve: `Nest manuali` + `Aggiusta qty ordine`.
5. Applica +2% operativo (se richiesto).
6. Compila fatture DC.
7. Controlla riepilogo DC.
8. Genera documenti.
9. Scarica tutto.
10. Segna spedito.
