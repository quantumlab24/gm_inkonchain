# 🧠 GM INKONCHAIN — Automatic GM Sender on INKONCHAIN Network

This script automatically interacts with [gm.inkonchain.com](gm.inkonchain.com) using EVM wallets listed in an Excel file. Supports proxies and multithreading.

---

## 🚀 Key Features

- 🔐 Supports both seed phrases and private keys
- 🌐 RPC InkChain (InkonChain + 3rd-party)
- 🕒 Checks time since last GM transaction (`lastGM`)
- 🧵 Multithreaded execution
- 🌍 Supports HTTP/SOCKS proxies (with optional login:password)
- 🧾 Logs results and errors back to `gm_ink.xlsx`

---

## 📁 Project Structure

| File               | Description                              |
|--------------------|-------------------------------------------|
| `main.py`          | Main script with execution logic          |
| `gm_ink.xlsx`      | Excel file with wallets and results       |
| `requirements.txt` | Required dependencies                     |
| `excel_functions.py` | Excel read/write helpers                |
| `utils.py`         | Logging and helper utilities              |

---

## 📋 Excel Format: `gm_ink.xlsx`

| NUMBER_WALLET | EVM_SEED_PHRASE | EVM_WALLET_ADDRESS | EVM_PRIVATE_KEY | PROXY      | STATUS | ERROR_ID | GM_INK         |
|---------------|------------------|---------------------|------------------|------------|--------|----------|----------------|
| 1             | seed or blank     | address or blank    | key or blank     | no_proxy   | TRUE   | —        | GM result       |

- **PROXY** can be:
  - `no_proxy` – to send GM without proxy
  - `IP:PORT`
  - `LOGIN:PASS@IP:PORT`
  - Optional with protocol (`http://`, `socks5://`) e.g. `http://user:pass@host:port` or `socks5://user:pass@host:port`
- **EVM_WALLET_ADDRESS** and **EVM_PRIVATE_KEY** can be left blank — they’ll be auto-generated from the seed phrase if present.
- If **EVM_SEED_PHRASE** is missing, only provide private keys.

---

## ⚙️ Installation

1. Make sure Python 3.11+ is installed.
2. Install dependencies:

```bash
python -m venv .venv
```
```bash
.venv\Scripts\activate
```
```bash
pip install -r requirements.txt
```

Contents of `requirements.txt`:
```text
requests~=2.32.3
web3~=7.8.0
loguru~=0.7.3
eth-account~=0.13.5
mnemonic~=0.21
openpyxl~=3.1.5
eth-keys~=0.6.1
bip32utils~=0.3.post4
pandas~=2.2.3
```

---

## ▶️ Usage

```bash
python main.py
```

Before running:

- The `STATUS` column must be cleared! If filled, wallets will be skipped.

After running:

- All valid accounts from Excel will be processed;
- Script checks if 24h passed since last `gm()` call;
- Results are written to `GM_INK`, errors to `ERROR_ID`.

---

## ⚠️ Important

- The GM contract operates on **InkChain** (ChainID: 57073)
- Calls `gm()` method (no arguments)
- Script ensures 24h cooldown since last GM transaction

---

## 📄 License

Provided "as is" for educational purposes only. The author is not responsible for any consequences.

---