# Verified Paper Research (`vpr`) - Claude AI Skill

Anti-hallucination academic paper research and verification skill for Claude AI and Claude Code, built according to Anthropic's Agent Skills specification.

## 🎯 Overview
Ensures Claude only cites, quotes, and synthesizes findings from scientific papers whose full-text PDFs have been downloaded and validated in the current session.

## 📁 Repository Structure
```text
vpr/
├── SKILL.md              # Core skill instructions and frontmatter
├── mcp_server.py         # MCP JSON-RPC Server with SSRF guard & persistent rate limiting
└── scripts/
    ├── render_kanban.py  # Static HTML Kanban viewer from ledger.json (safe href, XSS-guarded)
    └── sandbox_worker.py # Sandbox worker with domain whitelist, max 50MB, and auditable ledger
.github/
└── workflows/
    └── vpr-sandbox.yml   # Workflow dispatch runner for Claude sandbox offloading
docs/
└── index.html            # Visual interactive workflow web app
tests/
└── test_vpr.py           # Unit tests (clean_url, safe_href, SSRF check, PDF validation)
LICENSE                   # MIT License (Siti Maryam)
```

## 🔒 Keamanan & Integritas Data (Security Hardening v1.0.2)
- **Data vs Instruksi**: Seluruh isi berkas paper dan respons remote diperlakukan murni sebagai **DATA**, bukan instruksi sistem (mencegah *prompt injection* laten).
- **Proteksi SSRF & Domain Whitelist**: Mengisolasi unduhan hanya ke domain akademik terpercaya (`arxiv.org`, `export.arxiv.org`), menolak alamat IP lokal/privat (`127.0.0.1`, `localhost`, `10.x.x.x`), memeriksa URL pasca-redirect, dan membatasi berkas maksimal 50 MB.
- **Buku Besar Auditable**: Setiap entri `ledger.json` dilengkapi tanda tangan hash `sha256`, timestamp pengambilan `retrieved_at`, jumlah halaman, dan persentase keselarasan judul minimum 60%.
- **Remote Fetch Opt-In**: Penarikan teks remote dari repositori dinonaktifkan secara bawaan kecuali pengguna secara eksplisit mengaktifkan `VPR_ALLOW_REMOTE=1`, dengan pelabelan `untrusted_remote`.
- **Mode Tanpa MCP**: Pengguna Claude.ai yang mengunggah berkas `.zip` dapat menjalankan seluruh alur verifikasi secara mandiri tanpa memerlukan server MCP.

## ⚖️ License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Copyright (c) 2026 Siti Maryam (`maryam0508`).

## 🌐 Interactive Workflow Web
- **Live Documentation**: [https://maryam0508.github.io/vpr-claude-skill/](https://maryam0508.github.io/vpr-claude-skill/)
- Hosted 100% on GitHub Pages (static, zero-server load). Interactive 6-stage execution flowchart and MCP server setup guides included.

## 🚀 Cara Pemasangan Mudah (Tanpa Perlu Terminal / Command Line)

Tidak perlu paham terminal Linux ataupun PowerShell. Ikuti 3 langkah klik sederhana berikut:

1. **Unduh Berkas Skill**:
   - Buka halaman [Releases v1.0.2](https://github.com/maryam0508/vpr-claude-skill/releases/tag/v1.0.2).
   - Klik dan unduh berkas **`vpr-claude-skill.zip`** ke komputer atau laptop kamu.

2. **Pasang di Claude.ai**:
   - Buka peramban dan masuk ke **Claude.ai**.
   - Klik menu profil di pojok kiri bawah, lalu pilih **Settings** atau **Customize**.
   - Pilih tab **Skills**.
   - Klik tombol **Upload Skill** (atau drag-and-drop berkas `.zip`), lalu pilih berkas `vpr-claude-skill.zip` yang baru diunduh.
   - Pastikan status skill aktif (toggle on).

3. **Gunakan Langsung**:
   - Buka percakapan baru dengan Claude dan minta topik riset apa saja, misalnya:
     > *"Carikan paper ilmiah tentang evaluasi keamanan AI terbaru dan sertakan sitasi terverifikasinya."*
   - Claude akan otomatis menjalankan protokol verifikasi VPR tanpa mengarang referensi.

---

## 🛠️ Pilihan: Pemasangan Mandiri via Docker (Self-Hosted Manual Deploy)
Bagi pengguna yang ingin menjalankan mesin pencari dan penampung berkas sendiri secara lokal:
1. Masuk ke direktori `deploy/`.
2. Jalankan `docker compose up -d`.
3. Lingkungan Docker sudah mencakup:
   - **SearXNG**: Mesin penelusur meta open access internal.
   - **VPR Worker Linux**: Penampung berkas dan konverter Markdown otomatis.
   - **Auto-Cleanup Daemon**: Pembersih otomatis berkas biner PDF setiap 10 menit agar disk tidak penuh.
