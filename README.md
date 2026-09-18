# Architecture Memory Engine (AME)

> **Persistent Architectural Memory for AI Coding Agents**

AME maintains a versioned architectural memory of software repositories and computes the minimum sufficient architectural context for AI coding agents.

```
                ┌─────────────────────┐
                │  GitHub / Local /   │
                │  IDE Workspace      │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │  Ingestion +        │
                │  Security Filter    │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │   AST + Inference   │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │ Versioned           │
                │ Architectural Graph │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │ Retrieval +         │
                │ Impact Analysis     │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │ Minimum Context     │
                │ + Provenance        │
                └──────────┬──────────┘
                           ↓
                       MCP / REST
                           ↓
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
        Codex         Antigravity       Other Agent
```

## Features

- **Multi-Source Ingestion**: Ingest from local Git repositories, GitHub clones, or live IDE workspace uncommitted buffers.
- **Repository Snapshots**: Central state model tracking `Repository -> (Commit Snapshot | Branch Snapshot | Workspace Snapshot [committed + uncommitted]) -> Graph`.
- **Confidence & Provenance**: Every edge carries confidence (0.0–1.0) and source type (`static_analysis`, `framework_inference`, etc.). Every context snippet carries full provenance (file, line span, commit/snapshot, relationship chain).
- **Core Impact Analysis**: First-class engine answering *"What could my change break?"* before modifying code.
- **Greedy Minimum-Context Selection**: Balances relevance vs. token cost to package minimum sufficient context under strict token budgets (e.g. 8,000 tokens).
- **Agent-Agnostic MCP Server**: Integrates with Codex, Antigravity, Cursor, Claude Desktop, and other agents via standard Model Context Protocol tools.
