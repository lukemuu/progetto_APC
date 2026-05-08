# Analisi e Mitigazione di Replay Attack tramite Rolling Code

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

## 🛠️ Hardware Utilizzato
* **Microcontrollori:** 2x STM32F303 Discovery Board.
* **Comunicazione Wireless:** 3x Transceiver HC-12 (433MHz).
* **Interfaccia PC:** 1x Adattatore USB-UART (CH340).
* **Attuatori:** * 1x Modulo Relè (5V).
    * 1x Mini Serratura Elettromagnetica (12V).
    * 1x Buzzer Attivo.
* **Alimentazione:** Portapile per 8 batterie AA (12V) per il circuito di potenza della serratura.
* **Varie:** Breadboard, cavi Jumper (Dupont), Diodo 1N4007 per protezione da picchi induttivi.

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

---

## 🚀 Come avviare il progetto

### 1. Configurazione Firmware
Importare i progetti `Nodo1` e `Nodo2` in STM32CubeIDE, compilarli e caricarli sulle rispettive schede Discovery.

### 2. Configurazione Dashboard Python
Assicurarsi di avere Python installato, collegare l'adattatore USB-UART e lanciare:
```bash
pip install pyserial customtkinter
python main_hacker.py
