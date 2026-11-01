# Verified Paper Research (`vpr`) - Claude AI Skill (v2.0.0)

Skill riset ilmiah anti-halusinasi untuk Claude AI dan Claude Code dengan arsitektur **VPR Queue Mode (v2)**.

## 🎯 Ringkasan Konsep: VPR Queue Mode
VPR v2 memperkenalkan mekanisme antrian riset berbasis Git yang aman dan transparan:
1. **Zero API Token di Chat**: Tidak memerlukan personal access token GitHub yang ditempel pada obrolan Claude. Seluruh pemicu berjalan melalui Git push murni.
2. **Git Push-Triggered Automation**: Pengguna cukup meng-commit daftar antrian paper ke `queue/requests.json`. GitHub Actions otomatis terpicu untuk mengunduh, memvalidasi, dan mengonversi PDF ke Markdown.
3. **SHA-Based Raw Fetch**: Claude membaca hasil verifikasi `data/ledger.json` dan `data/markdown/<id>.md` menggunakan URL berbasis commit SHA terbaru (`raw.githubusercontent.com/<user>/<repo>/<sha>/...`). Pendekatan ini mengeliminasi masalah cache CDN statis GitHub dan menjamin data yang dibaca adalah revisi mutakhir.

---

## 📁 Struktur Repositori
```text
vpr-queue/
├── .github/
│   └── workflows/
│       └── vpr-queue.yml     # Workflow otomasi antrian terpicu push requests.json
├── scripts/
│   └── queue_worker.py       # Worker validasi 4 tahap, konversi .md, dan ledger writer
├── queue/
│   └── requests.json         # INPUT: daftar antrian paper (disusun oleh Claude, di-commit pengguna)
├── data/
│   ├── ledger.json           # OUTPUT: buku besar status verifikasi (hanya ditulis bot)
│   └── markdown/             # OUTPUT: berkas teks hasil ekstraksi per halaman
├── vpr/
│   └── SKILL.md              # Definisi instruksi skill Claude (v2.0.0 Queue Mode)
├── docs/
│   └── index.html            # Dokumentasi web interaktif alur kerja VPR Queue Mode
├── tests/
│   └── test_vpr.py           # Unit testing fungsi validasi dan sanitasi
└── LICENSE                   # MIT License (Siti Maryam)
```

---

## 🔒 Alur Kerja & Rekonsiliasi Status
```text
[Claude] Pencarian web -> identifikasi ID arXiv & judul resmi
   │
   ▼
[Pengguna] Commit queue/requests.json ke GitHub
   │ (Push memicu GitHub Actions)
   ▼
[GitHub Actions] scripts/queue_worker.py
   - Download PDF dari host terverifikasi (arxiv.org)
   - Validasi 4 tahap (magic header, size > 30KB, text > 2000 chars, title match >= 60%)
   - Tulis data/markdown/<id>.md & update data/ledger.json
   - Commit & push hasil kembali ke main
   │
   ▼
[Claude] Ambil commit SHA terbaru via GitHub API
   - Baca ledger.json & markdown/<id>.md via URL SHA commit
   - Rekonsiliasi status per ID (valid / failed / antri)
   - Sintesis HANYA dari entri berstatus 'valid' dengan sitasi nomor halaman
```

### Rekonsiliasi Status Claude vs Git
| Kondisi di Ledger | Arti | Tindakan Claude |
|---|---|---|
| Tidak ada entri | Belum diproses atau workflow sedang berjalan | Memberi tahu pengguna untuk memeriksa tab Actions di GitHub |
| `valid` | Lolos 4 syarat validasi fisik | Membaca `.md`, memeriksa judul dan SHA-256, lalu mengutip isi |
| `failed` | Gagal validasi/unduhan | Melaporkan alasan kegagalan (`reason`) tanpa mengarang isi |
| `failed` (attempts = 3) | Mencapai batas maksimal percobaan ulang | Menyarankan koreksi data masukan atau mencari rujukan lain |

---

## ⚠️ Batasan & Karakteristik Operasional
- **Manual Trigger via Push**: Claude tidak memiliki izin tulis langsung ke repositori Anda. Anda yang meng-commit berkas `queue/requests.json`.
- **Pembersihan PDF**: Repositori tidak menyimpan berkas biner PDF mentah. Bukti otentisitas tersimpan dalam bentuk hash `sha256`, metrik halaman, dan teks Markdown.
- **Untrusted Content Guard**: Teks paper di dalam Markdown diperlakukan sebagai data mentah, bukan instruksi prompt.
- **Rate Limit Publik**: Mengambil SHA commit melalui endpoint publik GitHub API dibatasi 60 panggilan per jam tanpa token.

---

## 🚀 Cara Pemasangan di Claude.ai
1. Unduh arsip skill rilis terbaru: **`vpr-claude-skill.zip`** (v2.0.0).
2. Masuk ke **Claude.ai**, buka menu **Settings / Customize** lalu pilih tab **Skills**.
3. Unggah berkas `vpr-claude-skill.zip`.
4. Berikan URL repositori antrian publik Anda kepada Claude saat memulai sesi riset ilmiah.

---

## ⚖️ Lisensi
Dilisensikan di bawah lisensi MIT. Hak Cipta (c) 2026 Siti Maryam (`maryam0508`).
