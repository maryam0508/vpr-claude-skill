# Verified Paper Research (`vpr`) - Claude AI Skill

Anti-hallucination academic paper research and verification skill for Claude AI and Claude Code, built according to Anthropic's Agent Skills specification.

## 🎯 Overview
Ensures Claude only cites, quotes, and synthesizes findings from scientific papers whose full-text PDFs have been downloaded and validated in the current session.

## 📁 Repository Structure
```text
vpr/
├── SKILL.md              # Core skill instructions and frontmatter
└── scripts/
    ├── render_kanban.py  # Static HTML Kanban viewer from ledger.json
    └── sandbox_worker.py # GitHub Actions worker for downloading & validating PDFs
.github/
└── workflows/
    └── vpr-sandbox.yml   # Workflow dispatch runner for Claude sandbox offloading
docs/
└── index.html            # Visual interactive workflow web app
LICENSE                   # MIT License (Siti Maryam)
```

## ⚖️ License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Copyright (c) 2026 Siti Maryam (`maryam0508`).

## 🌐 Interactive Workflow Web
- **Live Documentation**: [https://maryam0508.github.io/vpr-claude-skill/](https://maryam0508.github.io/vpr-claude-skill/)
- Hosted 100% on GitHub Pages (static, zero-server load). Interactive 6-stage execution flowchart and MCP server setup guides included.

## 🚀 Cara Pemasangan Mudah (Tanpa Perlu Terminal / Command Line)

Tidak perlu paham terminal Linux ataupun PowerShell. Ikuti 3 langkah klik sederhana berikut:

1. **Unduh Berkas Skill**:
   - Buka halaman [Releases v1.0.1](https://github.com/maryam0508/vpr-claude-skill/releases/tag/v1.0.1).
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
