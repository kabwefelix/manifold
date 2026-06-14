# Manifold — Autonomous Cognitive Architecture

An AI system that doesn't just respond — it *learns, investigates, and evolves on its own*.

Manifold is a multi-agent cognitive architecture where AI agents autonomously identify knowledge gaps, formulate hypotheses, investigate using real tools (code execution, web research, data analysis), and synthesize actionable insights across domains — from algorithm efficiency to logistics to financial markets.

## What It Does

- **Self-directed learning** — detects gaps in its own understanding and initiates research
- **Multi-agent coordination** — orchestrates parallel agents for task decomposition and synthesis
- **Persistent memory** — maintains a cognitive ledger of insights, hypotheses, and verified knowledge
- **Tool-augmented reasoning** — runs Python, accesses the web, queries APIs — not just text generation
- **Continuous self-improvement** — tracks its own development actions and adapts cognitive weights over time

## How It Works

```
┌─────────────────────────────────────────────┐
│                 Manifold                     │
│                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │  Genesis  │──▶│Orchestrator│──▶│  Agents  │ │
│  │  (Start)  │   │(Coordinator)│  │(Workers) │ │
│  └──────────┘   └──────────┘   └──────────┘ │
│                         │                    │
│                    ┌────▼─────┐              │
│                    │  Tools    │              │
│                    │ (Code/Web)│              │
│                    └──────────┘              │
│                         │                    │
│              ┌──────────▼──────────┐         │
│              │   Memory Ledger    │         │
│              │ (Insights/History) │         │
│              └────────────────────┘         │
└─────────────────────────────────────────────┘
```

1. **Genesis** triggers an investigation cycle — usually targeting a knowledge gap or anomaly
2. **Orchestrator** decomposes the task and assigns sub-tasks to agents
3. **Workers** execute independently (code, research, analysis) and return findings
4. **Synthesis** combines results into structured insights stored in the Memory Ledger
5. **Self-development** tracks what it learned and adjusts its future behavior

## Real Example Insights Generated

- *"For small datasets (n < ~1000), O(n) linear search can outperform O(log n) binary search due to cache locality..."*
- *"Proactive monitoring of foreign regulatory bodies could provide early warning signals for importers facing supply chain disruptions..."*
- *"Q2 2024 Energy sector earnings surprises (+5.2%) correlated with negative returns (−1.8%), suggesting ESG transition risk discounting..."*

## Tech Stack

- **Runtime**: Python 3.11+
- **API**: FastAPI + Uvicorn
- **Storage**: SQLite + JSON ledger
- **Cross-model**: OpenAI, DeepSeek, Anthropic compatible

## Quick Start

```bash
# Clone
git clone https://github.com/kabwefelix/manifold.git
cd manifold

# Install
pip install -r requirements.txt

# Run
python -m manifold
```

## Project Structure

```
manifold/
├── manifold/               # Core system
│   ├── cognitive_weights.json    # Adaptive agent weights
│   ├── MEMORY_LEDGER.json        # Persistent knowledge store
│   ├── INSIGHTS.md               # Generated insights
│   ├── SELF_DEV_ACTIONS.jsonl    # Self-improvement log
│   └── skills/                   # Agent capabilities
├── requirements.txt
└── start-manifold.cmd            # Windows launcher
```

## Status

**v1.0** — Actively developed as a flagship cognitive architecture project. Built to demonstrate autonomous AI agent capabilities beyond simple chatbots.

## Author

**Felix Kabwe** — Independent AI developer and researcher.

- GitHub: [@kabwefelix](https://github.com/kabwefelix)
- Location: China / Zambia

---

*"I build things that think."*
