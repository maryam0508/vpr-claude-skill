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

## 🚀 How to Install

### Option 1: Claude.ai (Web / Desktop)
1. Download or package the `vpr` folder into `vpr.zip`.
2. Open Claude.ai → **Customize** → **Skills**.
3. Upload the ZIP file and enable the skill.

### Option 2: Claude Code (CLI)
Copy the `vpr` directory into your project's `.claude/skills/` folder:
```bash
cp -r vpr /path/to/project/.claude/skills/
```
