# Analisi e Mitigazione di Replay Attack tramite Rolling Code nei sistemi Keyless

## 🔐 Descrizione del Progetto
Questo progetto mira a dimostrare le vulnerabilità dei sistemi di accesso wireless (come telecomandi per auto o cancelli) ai cosiddetti **Replay Attack** e come implementare una contromisura efficace basata sull'algoritmo **Rolling Code**.

Il sistema simula una serratura intelligente controllata via radio, composta da un trasmettitore legittimo (Chiave), un ricevitore sicuro (Serratura) e una postazione di monitoraggio/attacco (Hacker Dashboard).

---

## 🏗️ Architettura del Sistema
Il sistema è suddiviso in tre nodi logici:

1.  **Nodo 1 - La Chiave (STM32F303):** Genera e invia pacchetti radio cifrati. Ogni invio incrementa un contatore interno, rendendo ogni codice univoco e utilizzabile una sola volta.
2.  **Nodo 2 - La Serratura (STM32F303):** Riceve il segnale, lo decifra e verifica se il contatore ricevuto è coerente con la propria "finestra di accettazione". In caso positivo, attiva un **Relè** collegato a una **Miniserratura solenoide**; in caso negativo (codice già usato o errato), attiva un allarme acustico tramite **Buzzer**.
3.  **Nodo 3 - Hacker Dashboard (PC + Python):** Utilizzando un adattatore USB-UART e un modulo radio, questo nodo "sniffa" il traffico nell'aria. L'interfaccia grafica permette di visualizzare i dati intercettati e tentare un **Replay Attack** (ri-invio di un codice precedentemente catturato).

---

## 🎬 Scenari di Dimostrazione

Il progetto prevede due scenari dimostrativi contrapposti, pensati per illustrare concretamente il problema della sicurezza e l'efficacia della soluzione adottata.

### Scenario 1 — Attacco con Successo (Sistema Senza Cifratura) 🔓

In questo scenario il firmware della Chiave trasmette il codice di apertura **in chiaro**, senza alcuna cifratura né meccanismo di rolling code. L'obiettivo è simulare il comportamento di un sistema di accesso wireless "naïf", ancora diffuso in dispositivi economici o datati.

**Flusso della dimostrazione:**
1. La Chiave invia il segnale di apertura via radio. Il modulo HC-12 dell'Hacker Dashboard intercetta il pacchetto.
2. Sull'interfaccia grafica (Nodo 3) il payload appare **in chiaro e leggibile** (es. `OPEN:1234`), immediatamente comprensibile.
3. L'operatore dell'Hacker Dashboard preme il pulsante **"Replay Attack"**: il codice catturato viene ritrasmesso alla Serratura.
4. La Serratura non ha modo di distinguere il pacchetto legittimo da quello ritrasmesso dall'attaccante: **la serratura si apre**, il relè scatta e la miniserratura solenoide si sblocca.

> **Risultato:** L'attacco ha successo. Un singolo pacchetto sniffato è sufficiente per ottenere accesso illimitato al sistema.

---

### Scenario 2 — Attacco Fallito (Sistema con Rolling Code) 🔒

In questo scenario il firmware è quello completo e sicuro: la Chiave cifra ogni pacchetto e incrementa il contatore interno ad ogni trasmissione. La Serratura mantiene sincronizzato il proprio contatore e accetta solo codici mai visti in precedenza, ricadenti nella propria finestra di accettazione.

**Flusso della dimostrazione:**
1. La Chiave invia il segnale di apertura. L'Hacker Dashboard intercetta il pacchetto ma questa volta il payload appare **cifrato e non interpretabile** (es. `A3F7C2B1...`): il contatore e il comando sono offuscati.
2. L'utente legittimo ha già aperto la serratura con quel pacchetto: il contatore della Serratura si è avanzato.
3. L'operatore dell'Hacker Dashboard preme il pulsante **"Replay Attack"** e ritrasmette il codice catturato.
4. La Serratura riceve il pacchetto, lo decifra e confronta il contatore con la propria finestra di accettazione: il valore è già stato usato (o è fuori finestra). **L'accesso viene negato** e il Buzzer emette un segnale di allarme acustico.

> **Risultato:** L'attacco fallisce. Il codice catturato è "bruciato" dopo il primo utilizzo legittimo e non può essere riutilizzato da un attaccante.

---

## 🛠️ Hardware Utilizzato
* **Microcontrollori:** 2x STM32F303 Discovery Board.
* **Comunicazione Wireless:** 3x Transceiver HC-12 (433MHz).
* **Interfaccia PC:** 1x Adattatore USB-UART (CH340).
* **Attuatori:**
    * 1x Modulo Relè (5V).
    * 1x Mini Serratura Elettromagnetica (12V).
    * 1x Buzzer Attivo.
* **Alimentazione:** Portapile per 8 batterie AA (12V) per il circuito di potenza della serratura.
* **Varie:** Breadboard, cavi Jumper, Diodo 1N4007 per protezione da picchi induttivi.

---

## 💻 Tecnologie e Software
* **Firmware (STM32):** Scritto in C utilizzando **STM32CubeIDE** con astrazione HAL e gestione della UART tramite **DMA** (per evitare il blocco della CPU durante gli attacchi DoS/Fuzzing).
* **Hacker Interface (PC):** Sviluppata in **Python** con librerie `pyserial` (comunicazione) e `customtkinter` (GUI moderna).
* **Algoritmo di Sicurezza:** Implementazione custom di un protocollo Rolling Code con finestra di sincronizzazione.

---

## 📂 Struttura della Repository
* `/Nodo1_Chiave`: Progetto STM32CubeIDE per il trasmettitore.
* `/Nodo2_Serratura`: Progetto STM32CubeIDE per il ricevitore e la gestione hardware della serratura.
* `/Nodo3_Hacker`: Script Python per la dashboard di sniffing e attacco.
* `/Docs`: Eventuali schemi elettrici e documentazione aggiuntiva.
