# 👻 PhantomBox

> **Secure Distributed Storage — Files that vanish when you're done with them.**

PhantomBox is an open-source, zero-permanent-storage file security system. Files are shredded into encrypted hologram noise fragments, distributed across isolated storage nodes, and reconstructed **only in RAM** on demand — then instantly wiped. Nothing is ever stored permanently on disk.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)](https://flask.palletsprojects.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

---

## Table of Contents

- [What is PhantomBox?](#what-is-phantombox)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the System](#running-the-system)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Security Model](#security-model)
- [Contributing](#contributing)
- [License](#license)

---

## What is PhantomBox?

PhantomBox is built around a simple but powerful idea: **a file that doesn't exist on disk cannot be stolen from disk.**

When you upload a file:
1. It is encrypted with **AES-256-GCM** using HKDF-derived keys
2. Split into **3 hologram noise fragments** (meaningless binary blobs individually)
3. Distributed across **isolated storage nodes**
4. A cryptographic record is written to the **PhantomNet blockchain**
5. The original file is discarded from memory

When you download a file:
1. The fragment map is fetched from the blockchain
2. All fragments are retrieved and **decrypted in RAM only**
3. The file is handed to you
4. Memory is **securely wiped** (3-pass overwrite) immediately after

No file ever sits permanently on a disk in readable form.

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                    Browser / Client                    │
│              (index.html + JS modules)                 │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP/REST
┌───────────────────────▼────────────────────────────────┐
│              PhantomBox App  :8000                     │
│   Flask · RBAC · JWT · Upload · Download · Share       │
└──────┬──────────────────────────┬──────────────────────┘
       │ Register / Verify        │ Fragment Dispersal
┌──────▼──────────┐    ┌──────────▼──────────────────────┐
│  PhantomNet     │    │      Noise Storage Nodes         │
│  Blockchain     │    │  Node A :9001  │  Node B :9002   │
│  Genesis :5001  │    │  (encrypted fragments on disk)   │
│  Peer    :5002  │    └─────────────────────────────────-┘
└─────────────────┘
```

### Three Layers

| Layer | Component | Purpose |
|---|---|---|
| **Blockchain** | PhantomNet (PoA) | Immutable metadata & fragment map |
| **Application** | PhantomBox (Flask) | Encryption, dispersal, reconstruction |
| **Storage** | Noise Nodes | Store meaningless encrypted fragments |

---

## Features

- 🔐 **AES-256-GCM encryption** with HKDF key derivation per fragment
- 🧩 **Hologram noise sharding** — 2-of-3 threshold reconstruction
- ⛓️ **Proof-of-Authority blockchain** for tamper-proof audit trail
- 🧠 **RAM-only reconstruction** — no plaintext ever touches disk
- 💨 **Secure memory wipe** (3-pass) after every download
- 👤 **RBAC** — Users own their files; Admins see everything
- 👻 **Ephemeral share links** — self-destruct after N downloads or expiry
- 🛡️ **Admin control panel** — users, files, audit logs, security monitor
- 🔑 **JWT authentication** backed by MySQL + bcrypt
- 📋 **Full audit ledger** — every upload, download, and share logged
- 🖥️ **Live dashboard** — blockchain height, node health, RAM usage

---

## Tech Stack

| Category | Technology |
|---|---|
| Backend | Python 3.10+, Flask 3.0, Flask-CORS |
| Auth | JWT (PyJWT), bcrypt, MySQL |
| Encryption | cryptography (AES-256-GCM, HKDF), pycryptodome |
| Blockchain | Custom Proof-of-Authority (pure Python) |
| Database | MySQL 8+ (auth, registry, audit) |
| Frontend | Vanilla HTML/CSS/JS (no build step) |
| Storage Nodes | Flask microservices |

---

## Prerequisites

- Python 3.10 or higher
- MySQL 8.0 or higher
- pip
- (Optional) 4 separate terminals or a process manager like `tmux`

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/phantombox.git
cd phantombox

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Database Setup

Run the SQL setup script against your MySQL server:

```bash
mysql -u root -p < phantombox/phantombox_db_setup.sql
```

This creates the `phantombox_db` database with all required tables:
- `users` — accounts and auth
- `file_registry` — file ownership records
- `audit_ledger` — immutable event log
- `user_sessions` — active sessions
- `shared_links` — ephemeral share tokens

---

## Environment Variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Key variables:

```env
# AES Key Derivation Secret — change this!
SYSTEM_SECRET=your_super_secure_random_secret_here

# MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=phantombox_db

# JWT — change this!
JWT_SECRET=your_jwt_secret_here

# Admin registration key (required to create Admin accounts)
ADMIN_SECRET_KEY=your_admin_key_here

# Node URLs
GENESIS_NODE=http://127.0.0.1:5001
PEER_NODE=http://127.0.0.1:5002
PHANTOMBOX_URL=http://127.0.0.1:8000
NOISE_NODES=http://127.0.0.1:9001,http://127.0.0.1:9002

# Ports
BLOCKCHAIN_PORT=5001
PEER_PORT=5002
PHANTOMBOX_PORT=8000
NOISE_NODE_PORTS=9001,9002

# File limits
FRAGMENT_COUNT=3
MIN_FRAGMENTS=2
MAX_FILE_SIZE=10485760   # 10 MB
```

> ⚠️ Never commit your `.env` file. It is listed in `.gitignore` by default.

---

## Running the System

Open **5 terminals** (or use tmux/screen) and run each component:

```bash
# Terminal 1 — Genesis Blockchain Node
python phantomnet/node.py genesis 5001 genesis

# Terminal 2 — Peer Blockchain Node
python phantomnet/node.py peer 5002 http://localhost:5001

# Terminal 3 — Noise Storage Node A
python phantombox/adapters/noise_node_A.py

# Terminal 4 — Noise Storage Node B
python phantombox/adapters/noise_node_B.py

# Terminal 5 — PhantomBox Application
python phantombox/app.py
```

Then open your browser at:

```
http://localhost:8000
```

### Using the Startup Scripts (Windows)

```bash
scripts/start_genesis.bat
scripts/start_peer.bat
scripts/start_noise_nodes.bat
scripts/start_phantombox.bat
```

---

## Project Structure

```
phantombox/
├── phantomnet/                  # Blockchain layer
│   ├── node.py                  # PoA blockchain node (Flask)
│   ├── blockchain.py            # Block & chain logic
│   ├── crypto_utils.py          # RSA signing, SHA-256
│   ├── registry.py              # File metadata registry
│   └── config.py
│
├── phantombox/                  # Application layer
│   ├── app.py                   # Flask app factory
│   ├── config.py
│   ├── routes/
│   │   ├── upload.py            # Encrypt & disperse
│   │   └── download.py          # Reconstruct & wipe
│   ├── services/
│   │   ├── aes_utils.py         # AES-256-GCM cipher
│   │   ├── pattern_engine.py    # Hologram noise generator
│   │   ├── dispersal.py         # Fragment distribution
│   │   ├── reconstruction.py    # RAM-only reconstruction
│   │   ├── preview_service.py   # Secure one-time previews
│   │   └── memory_store.py      # TTL memory store
│   ├── adapters/
│   │   ├── noise_node_A.py      # Storage node :9001
│   │   └── noise_node_B.py      # Storage node :9002
│   └── auth/
│       ├── __init__.py
│       ├── routes.py            # /api/auth/* endpoints
│       ├── admin_routes.py      # /api/admin/*, /api/share/*
│       ├── middleware.py        # jwt_required, admin_required
│       ├── mysql_service.py     # Auth business logic
│       ├── security.py          # bcrypt, JWT helpers
│       ├── db.py                # MySQL connection pool
│       ├── db_extensions.py     # Schema migrations
│       ├── models.py            # SQLAlchemy models (SQLite fallback)
│       └── share_service.py     # Ephemeral share links
│
├── client/                      # Frontend (no build step)
│   ├── index.html               # Main app shell
│   ├── auth.html                # Login / register
│   ├── share.html               # Public share link page
│   ├── app.js                   # Navigation & dashboard
│   ├── upload.js                # Upload flow
│   ├── download.js              # Download & preview
│   ├── history.js               # File history (server-backed)
│   ├── auth-guard.js            # RBAC enforcement
│   ├── lifecycle.js             # File lifecycle tracker
│   ├── metrics.js               # Security metrics widget
│   ├── explorer.js              # Blockchain explorer widget
│   └── admin/
│       └── index.html           # Admin control panel
│
├── phantombox/phantombox_db_setup.sql  # MySQL schema
├── tests/
│   └── test_blockchain.py
├── scripts/                     # Windows startup helpers
├── docs/
│   └── architecture.md
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Reference

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | None | Create account |
| POST | `/api/auth/login` | None | Get JWT token |
| GET | `/api/auth/me` | JWT | Current user profile |

### Files

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/upload` | JWT | Encrypt & disperse file |
| GET | `/api/request_download/<file_id>` | JWT | Reconstruct in RAM |
| GET | `/api/preview/<token>` | Token | One-time file preview |
| GET | `/api/download/<token>` | Token | One-time file download |
| GET | `/api/memory_stats` | None | RAM usage stats |

### Share Links

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/share/create` | JWT | Create ephemeral link |
| GET | `/api/share/list` | JWT | List your share links |
| DELETE | `/api/share/<id>` | JWT | Revoke a share link |
| GET | `/api/share/use/<token>` | None | Use a share link (public) |

### Admin

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/admin/stats` | Admin JWT | Dashboard stats |
| GET | `/api/admin/files` | Admin JWT | All files |
| GET | `/api/admin/users` | Admin JWT | All users |
| GET | `/api/admin/audit` | Admin JWT | Full audit log |
| GET | `/api/admin/security` | Admin JWT | Security monitor |
| GET | `/api/admin/blockchain` | Admin JWT | Blockchain explorer |

### History

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/history/uploads` | JWT | Your upload history |
| GET | `/api/history/downloads` | JWT | Your download history |

---

## Security Model

### Encryption

- **Algorithm:** AES-256-GCM (authenticated encryption)
- **Key derivation:** HKDF-SHA256 from `SYSTEM_SECRET` + per-fragment salt
- **Each fragment** gets its own unique nonce, auth tag, and salt
- **No key is stored anywhere** — keys are derived on-the-fly at reconstruction time

### Fragmentation

- Files are split into **3 fragments** with a **2-of-3 threshold**
- Each fragment is independently encrypted
- Fragments distributed across separate storage nodes
- Any single fragment alone is cryptographically meaningless

### Memory Security

- Reconstructed files are stored in `bytearray` (mutable, wipeable)
- **3-pass overwrite:** `0x00` → `0xFF` → `0x00` before deallocation
- Preview tokens have a **60-second TTL** and **one-time access**
- Download tokens have a **5-minute TTL** and **one-time access**
- Background cleanup thread purges expired tokens every 10 seconds

### Access Control

| Role | Can Upload | Can Download | Scope | Admin Panel |
|---|---|---|---|---|
| **User** | ✅ | ✅ (own files only) | Own files | ❌ |
| **Admin** | ✅ | ✅ (all files) | All files | ✅ |

### Blockchain

- Stores **metadata only** — no file content, no keys
- Stores fragment cipher hashes, nonces, and salts for integrity verification
- Tamper detection via SHA-256 chained hashing
- Two-node Proof-of-Authority for basic decentralization

---

## Running Tests

```bash
python -m pytest tests/
```

---

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests where applicable
4. Ensure all tests pass: `python -m pytest tests/`
5. Submit a pull request with a clear description of the change

Please open an issue first for major changes so we can discuss the approach.

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

---

## Roadmap

- [ ] Docker Compose setup for one-command launch
- [ ] Shamir's Secret Sharing for true cryptographic threshold reconstruction
- [ ] Email verification on signup
- [ ] Password reset via email
- [ ] S3-compatible noise node backend
- [ ] End-to-end test suite
- [ ] WebSocket live log streaming to dashboard
- [ ] Mobile-responsive UI improvements

---

## License

MIT License — see [LICENSE](LICENSE) for full text.

---

## Acknowledgements

Built as a demonstration of ephemeral, zero-permanent-storage security architecture. Inspired by concepts from distributed systems, cryptographic secret sharing, and secure memory management.

---

<p align="center">
  <strong>👻 PhantomBox — Your data exists only when you need it.</strong>
</p>