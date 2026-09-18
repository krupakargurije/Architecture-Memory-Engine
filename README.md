# Architecture Memory Engine (AME)

> **Persistent Architectural Memory for AI Coding Agents**

AME maintains a versioned architectural memory of software repositories and computes the minimum sufficient architectural and code context required by AI coding agents for development tasks.

```text
                ┌─────────────────────┐
                │ GitHub / Local /    │
                │ IDE Workspace       │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │ Ingestion +         │
                │ Security Filtering  │
                └──────────┬──────────┘
                           ↓
                ┌─────────────────────┐
                │ AST + Relationship  │
                │ Inference           │
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
                │ Minimum Context +   │
                │ Provenance          │
                └──────────┬──────────┘
                           ↓
                      MCP / REST
                           ↓
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
        Codex         Antigravity       Other Agent
```

---

## Overview

Modern AI coding agents (such as Codex, Antigravity, Claude Code, and Cursor) are capable of writing and editing code effectively, but struggle when operating in large, complex, and evolving repositories. Typically, an agent must repeatedly rediscover the structure of a codebase by scanning directory trees, grepping for symbols, or relying on heuristic file chunking.

**Architecture Memory Engine (AME)** is an **agent-agnostic infrastructure layer**—not another autonomous coding agent. It decouples architectural understanding from LLM inference by extracting, indexing, and maintaining an Architectural Knowledge Graph of the repository. When a coding task is submitted, AME traverses this graph to package only the relevant architectural dependencies, impacted services, covering tests, and targeted source spans under a strict token budget.

```text
Repository / IDE Workspace
        ↓
       AME
        ↓
Architectural Memory
        ↓
Minimum Relevant Context
        ↓
    MCP / REST
        ↓
  AI Coding Agent
```

---

## Why AME?

At repository scale, traditional AI coding context strategies encounter severe failure modes:

### 1. Full-Context Approaches
Dumping entire files or whole repository trees into the prompt window leads to:
* **Excessive Token Costs**: Consuming thousands of tokens on irrelevant boilerplate before the model reasons about the task.
* **Context Dilution & Distraction**: Models struggle to locate critical interfaces when buried in thousands of lines of unrelated implementations.
* **Lack of Structural Awareness**: Raw code dumps convey lexical ordering rather than architectural hierarchies.

### 2. Conventional Lexical / Vector Retrieval (RAG)
Chunk-based text or embedding search can retrieve fragments containing matching keywords, but fundamentally misses:
* **Dependency Chains**: A controller calling a service that uses a repository which accesses a table.
* **Caller / Callee Hierarchies**: Upstream clients that will break if a downstream signature changes.
* **Persistence & Data Paths**: Entity mappings, database operations, and schema dependencies.
* **API Endpoints & Contracts**: HTTP route annotations and payload boundaries.
* **Test Coverage**: Automated test suites that cover the affected component but do not mention the search query keywords.

### 3. Architectural Memory
AME models repository structure explicitly as a typed knowledge graph:

```text
OrderController
      ↓ CALLS
OrderService
      ↓ USES
DiscountService
      ↓ USES
DiscountRepository
      ↓ ACCESSES
Discount
```

The objective of AME is not merely to "retrieve similar code." The goal is:

> **Retrieve the smallest architecture-aware context that is sufficient for the task.**

---

## Core Idea

> **Instead of repeatedly asking an AI coding agent to rediscover the architecture of a repository, AME maintains that architectural knowledge as persistent structured memory and supplies the agent with only the context relevant to the current task.**

```text
Understand once / update incrementally
        ↓
Persistent architectural memory
        ↓
Task-specific retrieval
        ↓
Smaller model context
```

AME reduces repository exploration and retrieved context size. The downstream coding agent remains fully responsible for LLM reasoning, code synthesis, testing, and Git operations.

---

## Key Features

| Capability | Description |
| :--- | :--- |
| **Multi-Source Ingestion** | Ingests from local Git repositories, remote GitHub repositories, and IDE live buffer streams. |
| **Repository Snapshots** | Central state hierarchy tracking Commit Snapshots, Branch Snapshots, and uncommitted Workspace Snapshots. |
| **Architectural Graph** | Typed nodes (Controllers, Services, Repositories, Tables, Tests, APIs) and directed relationships. |
| **Relationship Confidence** | Distinguishes observed static relationships (`1.0`) from framework-inferred relationships (`0.85`). |
| **Explainable Provenance** | Every edge and snippet links to its exact file path, line span, snapshot ID, commit SHA, and traversal chain. |
| **Incremental Updates** | In-memory diff analyzer recalculates only altered nodes and edges without re-indexing the whole repository. |
| **Hybrid Retrieval** | BM25 lexical candidate discovery + multi-hop graph traversal + structural blast-radius analysis. |
| **Change Impact Analysis** | Computes upstream callers, downstream dependencies, touched tables, exposed APIs, and covering tests. |
| **Token-Budget Optimization** | Greedy relevance-per-token selection algorithm packing maximum value within user token constraints (e.g. 8k). |
| **Model Context Protocol (MCP)** | Standard JSON-RPC stdio server exposing 8 architectural tools to Antigravity, Codex, Cursor, and Claude. |
| **REST API** | High-performance FastAPI server with 11 endpoints for programmatic indexing, retrieval, and summaries. |
| **Interactive Graph UI** | Cytoscape.js visualizer with live query execution, dependency chains, impact tabs, JSON viewer, and graph VFX. |
| **Evaluation Suite** | Automated benchmark comparing Full Context vs. Vector RAG vs. AME across precision, recall, and token burn. |

---

## Architecture

The system operates across four primary pipeline stages:

```text
STAGE 1: Ingestion & AST Parsing
    Repository Files ──► Security Filter ──► Language Parser ──► Framework Inferrer
                                                                      │
STAGE 2: Knowledge Graph & Snapshots                                   ▼
    SQLite (Persistent) ◄── Versioned Snapshots ◄── Typed Nodes & Edges ──► NetworkX (In-Memory)
                                                                      │
STAGE 3: Architecture-Aware Retrieval                                 ▼
    Developer Task ──► Candidate Finder ──► Graph Traversal ──► Impact Analysis ──► Greedy Optimizer
                                                                                        │
STAGE 4: Agent Delivery                                                                 ▼
    AI Coding Agent ◄── Model Context Protocol (MCP) / REST ◄── ContextPackage (Prompt-Ready)
```

### Stage 1 — Repository Ingestion & Code Intelligence
Raw source code is ingested via local filesystem access or GitHub remote fetching. Files pass through a regex security filter before reaching dedicated language AST parsers.

#### Supported Languages:
* **Java**: Uses `javalang` to parse ASTs. Extracts:
  * Spring annotations: `@RestController`, `@Controller`, `@Service`, `@Repository`, `@Entity`, `@Table`.
  * HTTP mappings: `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`.
  * Dependency injection: `@Autowired` fields and constructor parameter injection.
  * Method declarations, call hierarchies, and JUnit `@Test` methods.
* **Python**: Uses standard library `ast` to parse ASTs. Extracts:
  * Classes, methods, synchronous and asynchronous functions.
  * Framework route decorators (`@app.get`, `@app.post`, Flask/FastAPI routing).
  * Data models: SQLAlchemy, Pydantic, and dataclasses.
  * Imports, inter-module function calls, and pytest `test_` functions.

### Stage 2 — Persistent Architectural Memory
AME maintains the knowledge graph using a hybrid storage model:
* **Persistent Storage**: Embedded SQLite database (`.ame/ame_graph.db`) with Write-Ahead Logging (WAL) for durability and ACID transactions.
* **Traversal Engine**: In-memory NetworkX directed multigraph (`MultiDiGraph`) reconstructed per snapshot for fast graph traversals.

#### Graph Entity Types (`EntityType`):
`repository`, `module`, `file`, `class`, `interface`, `function`, `method`, `service`, `controller`, `api`, `database`, `table`, `event`, `test`.

#### Graph Relationship Types (`RelationType`):
`CALLS`, `USES`, `DEPENDS_ON`, `IMPORTS`, `EXTENDS`, `IMPLEMENTS`, `EXPOSES_API`, `ACCESSES`, `READS_FROM`, `WRITES_TO`, `TESTED_BY`, `PUBLISHES`, `CONSUMES`.

#### Confidence & Provenance Model:
Edges differentiate between direct AST observations and framework inferences:
```json
{
  "source": "class:com.example.ecommerce.service.OrderService",
  "target": "class:com.example.ecommerce.repository.OrderRepository",
  "relation": "USES",
  "confidence": 0.85,
  "source_type": "framework_inference"
}
```

### Stage 3 — Architecture-Aware Retrieval & Impact Analysis
When a natural-language task is queried:
1. **Candidate Discovery**: Tokenizes the task and computes BM25 relevance across component names, signatures, and docstrings.
2. **Graph Traversal**: Conducts multi-hop bidirectional traversals starting from candidate seeds along semantic relationship types.
3. **Impact Analysis**: Evaluates ripple effects, upstream callers, database entities, exposed APIs, and covering tests.
4. **Snippet Extraction**: Pulls targeted source spans (class declarations, method bodies, or test signatures) rather than entire files.
5. **Token Optimization**: Executes greedy relevance-per-token selection to maximize context value within the token budget.

### Stage 4 — AI Agent Integration
The resulting `ContextPackage` is serialized and delivered directly to the agent runtime via Model Context Protocol (MCP) tool execution or REST API endpoints.

---

## GitHub Repository Analysis

AME supports analyzing remote GitHub repositories through an ephemeral ingestion pipeline:

```text
Paste GitHub URL (e.g. https://github.com/owner/repo)
                  ↓
       Resolve Remote Repository
                  ↓
    Ephemeral Analysis Workspace
                  ↓
   AST Parsing & Entity Extraction
                  ↓
     Build Architectural Graph
                  ↓
   Persist Graph Metadata in SQLite
                  ↓
     Delete Temporary Workspace
                  ↓
  Display Interactive Architecture Graph
```

* **Zero Full-Source Persistence**: The source code is acquired temporarily in memory or ephemeral workspace storage during parsing and is permanently cleaned up afterward. Only architectural metadata, node signatures, and relationship edges are stored in SQLite.
* **Failure Safety**: If remote repository resolution or analysis fails, the currently loaded repository snapshot remains intact and active.
* **Private Repository Support**: Accepts optional personal access tokens (`ghp_...`) for authenticated private repository access.

---

## Minimum-Context Retrieval

AME solves the context packaging problem as a constrained optimization problem:

$$\max \sum_{c \in C} \text{Relevance}(c, \text{Task}) \quad \text{subject to} \quad \sum_{c \in C} \text{Tokens}(c) \le B$$

Where $B$ is the user-defined token budget (e.g. 8,000 tokens).

### Greedy Relevance-Per-Token Selection
AME calculates an efficiency ratio for each candidate component:

$$\text{Efficiency}(c) = \frac{\text{RelevanceScore}(c)}{\text{TokenCost}(c)}$$

* **Candidate A**: Relevance = 0.95, Token Cost = 250 $\rightarrow$ Efficiency = 0.0038
* **Candidate B**: Relevance = 0.80, Token Cost = 900 $\rightarrow$ Efficiency = 0.0008
* **Candidate C**: Relevance = 0.91, Token Cost = 300 $\rightarrow$ Efficiency = 0.0030

High-efficiency architectural signatures, targeted method spans, dependency chains, and automated tests are prioritized over bulky, low-relevance implementation files.

---

## Change Impact Analysis

Before an AI agent alters code, AME answers: *"What could my change affect?"*

```text
Proposed Change: OrderService

CHANGE BLAST RADIUS:
├── Upstream Callers:       OrderController
├── Downstream Deps:        DiscountService, OrderRepository
├── Database Entities:      Order, Discount
├── Exposed APIs:           POST /api/orders
└── Covering Tests:         OrderServiceTest
```

### Risk Level Assessment
AME assigns structural risk ratings based on blast radius breadth:
* **LOW**: Isolated utility or component with no callers and no database touchpoints.
* **MEDIUM**: Standard service with 1–2 upstream callers or dependent unit tests.
* **HIGH**: Core domain service affecting public API contracts or multiple database tables.
* **CRITICAL**: Foundational interface or repository accessed across multiple modules.

> **Limitations Note**: AME performs structural and static impact analysis. Static analysis cannot guarantee detection of dynamic runtime reflection, runtime-generated proxies, or distributed network event payloads without trace instrumentation.

---

## Future Direction — Change Risk Prediction

The project roadmap includes extending structural impact analysis into statistical change-risk modeling:

```text
Developer proposes change
           ↓
Traverse Architectural Graph
           ↓
Identify Direct & Indirect Dependents
           ↓
Analyze Historical Git Log Co-Changes
           ↓
Correlate Recurring Regression Patterns
           ↓
Predict Failure Probability & Suggest Safety Tests
```

*Planned signals include*: historical co-change frequency, file churn rate, test failure history, and interface instability metrics. This represents future research and is not claimed as a current production capability.

---

## AI Coding Agent Integration

AME operates as an external architectural memory server for AI coding agents:

```text
                   AME Engine
                       │
             ┌─────────┴─────────┐
             │                   │
         FastAPI REST         MCP Server
          Port 8000           JSON-RPC
             │                   │
       ┌─────┴─────┐       ┌─────┴─────┐
       │ Browser UI│       │ AI Agents │
       └───────────┘       └─────┬─────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ↓               ↓               ↓
            Antigravity        Codex          Cursor
```

### Model Context Protocol (MCP) Tools

When configured as an MCP server, AME exposes 8 tools:

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `retrieve_context` | `task`, `repo_id`, `snapshot_id`, `token_budget` | Retrieves prompt-ready minimum context, dependency chains, and snippets. |
| `find_impact` | `component_name`, `repo_id`, `snapshot_id` | Computes structural blast radius, affected callers, APIs, and tests. |
| `find_call_chain` | `source`, `target`, `repo_id`, `snapshot_id` | Finds the shortest architectural dependency path between two components. |
| `find_dependencies` | `component_name`, `repo_id`, `snapshot_id`, `direction` | Returns upstream callers, downstream dependencies, or both. |
| `get_repository_architecture`| `repo_id`, `snapshot_id` | Returns high-level summary of controllers, services, tables, and APIs. |
| `get_related_tests` | `component_name`, `repo_id`, `snapshot_id` | Discovers unit and integration test suites covering a component. |
| `create_workspace_snapshot` | `repo_id`, `uncommitted_files`, `base_snapshot_id` | Ingests active in-memory IDE buffers to produce a live workspace snapshot. |
| `search_architecture` | `query`, `repo_id`, `snapshot_id`, `entity_type` | Keyword and symbol search across indexed architectural nodes. |

---

## Interactive Visualization

AME provides an interactive web dashboard powered by Cytoscape.js:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ AME — ARCHITECTURE MEMORY ENGINE                         [DEFAULT] [SWITCH] │
├──────────────────────────┬─────────────────────────────────┬────────────────┤
│ ACTIVE REPOSITORY        │ GRAPH CANVAS                    │ INSPECTOR      │
│ ecommerce_java           │                                 │ 1,253 / 8,000  │
│ 44 nodes · 59 edges      │     [OrderController]           │                │
│                          │            │                    │ Architecture   │
│ TASK RETRIEVAL           │          CALLS                  │ Source         │
│ [ Add Redis cache to  ]  │            ↓                    │ Impact         │
│ [ pricing service     ]  │      [PricingService]           │ Provenance     │
│ Budget: 8000             │            │                    │ Node           │
│ [ Retrieve Context ]     │          USES                   │ Benchmark      │
│                          │            ↓                    │                │
│ Recent Tasks:            │     [PricingRepository]         │ [Copy Context] │
│ ✓ Pricing Cache          │            │                    │ [View JSON]    │
│ ✓ OrderService Impact    │         ACCESSES                │ [Send to Agent]│
│                          │            ↓                    │                │
│                          │        [Product]                │                │
└──────────────────────────┴─────────────────────────────────┴────────────────┘
```

* **Dynamic Task Retrieval**: Enter any natural-language coding task; the UI triggers a 6-stage animated analysis progress panel (`Understanding task` $\rightarrow$ `Finding candidate components` $\rightarrow$ `Traversing architecture` $\rightarrow$ `Computing impact` $\rightarrow$ `Selecting relevant code` $\rightarrow$ `Optimizing context`).
* **Visual Graph Effects**: Dynamically dims unrelated nodes to 12% opacity, applies bright glowing highlights to retrieved nodes, and renders animated particle flow across active dependency edges.
* **Interactive Dependency Chains**: Renders clickable call paths in the Architecture tab; clicking any node focuses and centers the graph canvas.
* **Context Actions**: One-click actions to "Copy Context" (formatted markdown), "View JSON" (raw `ContextPackage` schema modal), or "Send to AI Agent" (MCP envelope payload).

---

## Token Efficiency

When evaluating token savings, AME distinguishes between two separate metrics:

### 1. Context Reduction
Measures the reduction in context volume passed to the agent compared to sending the entire repository source:

$$\text{Context Reduction} = \frac{\text{Full Repository Tokens} - \text{AME Retrieved Tokens}}{\text{Full Repository Tokens}} \times 100\%$$

* **Sample Ecommerce Repository**: Full context = 2,403 tokens.
* **Pricing Cache Task**: AME context = 1,253 tokens (**47.9% reduction**).
* **Coupon Rule Task**: AME context = 895 tokens (**62.8% reduction**).
* **Order Creation Task**: AME context = 1,521 tokens (**36.7% reduction**).

### 2. End-to-End Agent Token Burn
Measures the total model tokens consumed across the full agent lifecycle (exploration loops, search commands, repeated file reads, editing turns, and test runs):

$$\text{Token Burn Reduction} = \frac{\text{Baseline Total Tokens} - \text{AME Total Tokens}}{\text{Baseline Total Tokens}} \times 100\%$$

Because AME provides targeted dependency chains upfront, agents avoid iterative blind tool search calls and repeated file reads.

---

## Evaluation & Benchmarks

AME includes an automated multi-task benchmark runner (`python -m ame.evaluation.benchmark`) that compares three retrieval strategies on identical tasks under an 8,000-token budget:
1. **Full Repository Context**: Indiscriminately dumps all project source files.
2. **Vector / Lexical RAG**: Sliding-window 25-line chunk index (5-line overlap) ranked by term-frequency overlap.
3. **AME Architectural**: Minimum-context retrieval via knowledge graph traversal and greedy optimization.

### Benchmark Metrics Defined:
* **Context Precision**: Ratio of retrieved components that belong to the true task ground-truth dependency chain.
* **Dependency Recall**: Proportion of critical architectural dependency chain nodes successfully retrieved.
* **Test Recall**: Proportion of relevant test suites retrieved.
* **Agent Task Success @ 8k**: Composite score representing whether sufficient context was delivered to execute the change correctly within budget.

### Verified Multi-Task Benchmark Results:

```text
>> Task 1: Order Discount Validation (Transactional Flow)
Approach             | Tokens   | Precision  | Dep Recall  | Test Recall  | Agent Success @ 8k
----------------------------------------------------------------------------------------------
Full Context         | 2,403    | 0.61       | 1.00        | 1.00         | 0.923
Vector RAG           | 970      | 1.00       | 0.43        | 1.00         | 0.657
AME Architectural    | 2,184    | 1.00       | 1.00        | 1.00         | 1.000

>> Task 2: Product Pricing Quote Cache (Query Flow)
Approach             | Tokens   | Precision  | Dep Recall  | Test Recall  | Agent Success @ 8k
----------------------------------------------------------------------------------------------
Full Context         | 2,403    | 0.39       | 1.00        | 1.00         | 0.877
Vector RAG           | 773      | 1.00       | 1.00        | 0.00         | 0.800
AME Architectural    | 1,253    | 1.00       | 1.00        | 1.00         | 1.000

>> Task 3: Coupon Expiration Enforcement (Domain Rule Flow)
Approach             | Tokens   | Precision  | Dep Recall  | Test Recall  | Agent Success @ 8k
----------------------------------------------------------------------------------------------
Full Context         | 2,403    | 0.31       | 1.00        | 1.00         | 0.862
Vector RAG           | 1,017    | 0.40       | 0.67        | 0.00         | 0.480
AME Architectural    | 895      | 1.00       | 1.00        | 0.00         | 0.800
```

### Aggregate Mean Scores Across Tasks:

| Approach | Mean Tokens | Mean Precision | Mean Dep Recall | Mean Test Recall | Mean Agent Success |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Context** | 2,403 | 0.44 | 1.00 | 1.00 | 0.887 |
| **Vector RAG** | 920 | 0.80 | 0.70 | 0.33 | 0.646 |
| **AME Architectural** | **1,444** | **1.00** | **1.00** | **0.67** | **0.933** |

> *Evaluation Scope*: Results reflect the evaluated sample ecommerce codebase and ground-truth tasks. Retrieval efficiency varies based on repository scale, modularity, and architectural decoupling.

---

## Example Workflow

An end-to-end demonstration is implemented in [`scripts/demo_agent_loop.py`](file:///d:/antigravity_projects/Architecture%20Memory%20Engine/scripts/demo_agent_loop.py):

### 1. Developer Submits Task
```text
Task: "Introduce a discount validation step before creating an order"
```

### 2. Coding Agent Calls AME via MCP
```json
{
  "tool": "retrieve_context",
  "parameters": {
    "task": "Introduce a discount validation step before creating an order",
    "repo_id": "sample-ecommerce",
    "token_budget": 8000
  }
}
```

### 3. AME Returns Architectural Chain & Blast Radius
```text
Dependency Chain:
OrderController ──[CALLS]──► OrderService ──[USES]──► DiscountService ──[USES]──► DiscountRepository ──[ACCESSES]──► Discount

Impact Blast Radius:
- Upstream Callers: OrderController
- Downstream Dependencies: DiscountService, OrderRepository, Discount
- Database Entities: Discount
- Affected Tests: OrderServiceTest
- Assessed Risk Level: MEDIUM
```

### 4. Agent Synthesizes Code Change
The agent modifies `OrderService.java` to inject `DiscountService` and call `validateDiscountEligibility()` before saving the order.

### 5. Agent Submits Uncommitted Diff to AME
```json
{
  "tool": "create_workspace_snapshot",
  "parameters": {
    "repo_id": "sample-ecommerce",
    "uncommitted_files": {
      "src/.../OrderService.java": "<modified in-memory source content>"
    }
  }
}
```

### 6. AME Incremental Update
AME updates the knowledge graph incrementally:
* `invalidated_nodes`: 2
* `added_nodes`: 3
* `total_nodes`: 45
* New method indexed: `OrderService.validateDiscountEligibility`
* No full re-index required.

---

## Project Structure

```text
Architecture Memory Engine/
├── ame/                             # Core Python package
│   ├── api/                         # FastAPI REST application
│   │   └── app.py                   # REST endpoints and lifecycle handlers
│   ├── evaluation/                  # Benchmark suite & evaluation metrics
│   │   ├── benchmark.py             # Multi-task comparative benchmark runner
│   │   └── metrics.py               # Precision, recall, and success formulas
│   ├── graph/                       # Graph storage & schema management
│   │   ├── base.py                  # Abstract base graph store interface
│   │   ├── embedded_store.py        # SQLite + NetworkX hybrid implementation
│   │   └── versioning.py            # Snapshot and branch manager
│   ├── incremental/                 # Incremental update engine
│   │   ├── diff_analyzer.py         # Computes AST-level node/edge differences
│   │   └── updater.py               # Applies workspace deltas to active snapshots
│   ├── ingestion/                   # Multi-source repository ingestion
│   │   ├── base.py                  # Ingestion interfaces and data structures
│   │   ├── github_connector.py      # Ephemeral remote GitHub workspace ingestion
│   │   ├── ide_stream.py            # IDE uncommitted file stream buffer
│   │   ├── local_git.py             # Local filesystem and Git reader
│   │   └── pipeline.py              # Ingestion orchestration pipeline
│   ├── mcp/                         # Model Context Protocol (MCP) server
│   │   ├── server.py                # JSON-RPC 2.0 stdio protocol server
│   │   └── tools.py                 # High-level tool implementations
│   ├── models/                      # Pydantic data schemas
│   │   ├── context.py               # ContextPackage, Snippets, and ImpactSummary
│   │   ├── provenance.py            # ProvenanceRecord tracking model
│   │   ├── schema.py                # Node, Edge, EntityType, and RelationType
│   │   └── snapshot.py              # RepositorySnapshot and UncommittedChange
│   ├── parser/                      # Language AST parsers & relationship inference
│   │   ├── base.py                  # Abstract parser interface
│   │   ├── inferrer.py              # Framework convention inference rules
│   │   ├── java_parser.py           # Java AST parser (Spring, JPA, JUnit)
│   │   ├── python_parser.py         # Python AST parser (FastAPI, SQLAlchemy, pytest)
│   │   └── registry.py              # Parser file extension registry
│   ├── retrieval/                   # Context retrieval engine
│   │   ├── candidate_finder.py      # BM25 tokenized candidate discovery
│   │   ├── engine.py                # Master retrieval orchestration engine
│   │   ├── graph_traversal.py       # Multi-hop k-hop graph traversal algorithms
│   │   ├── impact_analyzer.py       # Ripple-effect and blast-radius analyzer
│   │   ├── optimizer.py             # Greedy relevance-per-token optimizer
│   │   ├── provenance_tracker.py    # Tracks audit trails for retrieved artifacts
│   │   ├── snippet_extractor.py     # Extracts minimal code spans from disk
│   │   └── summarizer.py            # High-level structural metrics summarizer
│   ├── security/                    # Security filters & credential protection
│   │   └── filter.py                # Regex pattern secret and binary filter
│   └── config.py                    # Global system configuration and defaults
├── frontend/                        # Interactive web visualizer
│   ├── app.js                       # Frontend controller, Cytoscape setup, and task UI
│   ├── index.html                   # Dashboard markup, task inputs, tabs, and modals
│   └── styles.css                   # Dark-mode styling, glowing VFX, and animations
├── samples/                         # Reference sample codebases
│   └── ecommerce_java/              # Spring Boot Java ecommerce reference repository
├── scripts/                         # Demonstrations and utility scripts
│   └── demo_agent_loop.py           # End-to-end AI agent loop demonstration
├── tests/                           # Comprehensive test suite (33 passing unit tests)
│   ├── test_agent_e2e_loop.py       # Agent workflow integration test
│   ├── test_default_and_switching.py# Repository auto-load and switching tests
│   ├── test_github_remote.py        # GitHub remote ingestion & cleanup tests
│   ├── test_graph_store.py          # SQLite graph store persistence tests
│   ├── test_impact_analyzer.py      # Blast radius analysis tests
│   ├── test_ingestion.py            # Ingestion & secret filter tests
│   ├── test_mcp.py                  # MCP server protocol tests
│   ├── test_parsers.py              # Java and Python AST parser tests
│   ├── test_retrieval_optimizer.py  # Greedy token optimizer tests
│   └── test_snapshot_incremental.py # Incremental update delta tests
├── .gitignore                       # Git ignore rules for SQLite, pycache, and logs
└── pyproject.toml                   # Project packaging and dependency specifications
```

---

## Getting Started

### Prerequisites
* Python `>= 3.10`
* Git installed and on your system `PATH`

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/krupakargurije/Architecture-Memory-Engine.git
cd Architecture-Memory-Engine
```

Install in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

Or install using standard `pip`:

```bash
pip install -e .
```

---

## Running AME

### 1. Launch the REST API & Web Dashboard
```bash
python -m uvicorn ame.api.app:app --host 127.0.0.1 --port 8000
```
Open your browser and navigate to:
```text
http://127.0.0.1:8000/
```
The dashboard automatically loads the default `ecommerce_java` reference repository (44 nodes, 59 edges) into the interactive workspace.

### 2. Launch the MCP Stdio Server (for AI Agents)
```bash
python -m ame.mcp.server
```
Configure this command in your AI coding agent's MCP settings (such as Antigravity, Claude Desktop, or Cursor) to grant the agent direct architectural memory access.

### 3. Run the Automated Test Suite
```bash
python -m pytest tests/ -v
```
Runs all 33 unit and integration tests covering parsers, graph storage, impact analysis, remote ingestion, and incremental updates.

### 4. Run the Comparative Benchmark
```bash
python -m ame.evaluation.benchmark
```
Executes the multi-task comparative evaluation between Full Context, Vector RAG, and AME.

### 5. Run the End-to-End Agent Demonstration
```bash
python scripts/demo_agent_loop.py
```
Simulates an agent retrieving context, analyzing impact, applying a code diff, and triggering an incremental workspace update.

---

## API

The FastAPI server provides 11 REST endpoints:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status check. |
| `GET` | `/api/default-repository` | Fetches metadata and snapshot ID for the default sample repository. |
| `GET` | `/api/repositories` | Lists all indexed repositories in the store. |
| `POST` | `/api/ingest` | Ingests a local repository directory path. |
| `POST` | `/api/github/ingest` | Ingests a remote GitHub repository via an ephemeral analysis workspace. |
| `GET` | `/api/architecture-summary/{snapshot_id}` | Returns entity counts, primary flows, and structural health metrics. |
| `GET` | `/api/graph/{snapshot_id}` | Returns serialized nodes and edges for graph canvas rendering. |
| `POST` | `/api/retrieve` | Retrieves minimum architectural context for an arbitrary coding task. |
| `GET` | `/api/impact/{repo_id}/{component_name}` | Computes the change blast radius for a named component. |
| `GET` | `/api/call-chain/{repo_id}` | Queries the shortest call chain between `source` and `target` components. |
| `POST` | `/api/workspace-snapshot` | Ingests uncommitted IDE buffer diffs to produce a new workspace snapshot. |

### Context Retrieval Request Example:
```http
POST /api/retrieve HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "task": "Add Redis caching to product pricing quote",
  "repo_id": "sample-ecommerce",
  "snapshot_id": "snap-215d4703e902",
  "token_budget": 8000
}
```

### Context Retrieval Response Example (Abbreviated):
```json
{
  "task": "Add Redis caching to product pricing quote",
  "repo_id": "sample-ecommerce",
  "snapshot_id": "snap-215d4703e902",
  "task_intent": "IMPLEMENTATION",
  "total_tokens": 1253,
  "token_budget": 8000,
  "token_savings_percentage": 47.85,
  "nodes_count": 4,
  "edges_count": 3,
  "snippets_count": 4,
  "impact": {
    "target_components": ["PricingController", "PricingService", "PricingRepository", "Product"],
    "upstream_callers": ["PricingController"],
    "downstream_dependencies": ["PricingRepository", "Product"],
    "affected_tests": ["PricingServiceTest"],
    "risk_level": "MEDIUM"
  },
  "dependency_chains": [
    { "source": "PricingController", "relation": "CALLS", "target": "PricingService", "confidence": 1.0 },
    { "source": "PricingService", "relation": "USES", "target": "PricingRepository", "confidence": 0.85 },
    { "source": "PricingRepository", "relation": "ACCESSES", "target": "Product", "confidence": 0.85 }
  ],
  "formatted_context": "# AME Architectural Context for Task: 'Add Redis caching to product pricing quote'..."
}
```

---

## MCP Tools

Example configuration for Claude Desktop or Antigravity (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "architecture-memory-engine": {
      "command": "python",
      "args": ["-m", "ame.mcp.server"],
      "cwd": "/path/to/Architecture-Memory-Engine"
    }
  }
}
```

### Direct MCP Tool Invocation Example (`retrieve_context`):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "retrieve_context",
    "arguments": {
      "task": "What will break if I change OrderService?",
      "repo_id": "sample-ecommerce",
      "token_budget": 8000
    }
  }
}
```

---

## Security & Privacy

AME is designed to operate safely on sensitive codebases:

* **Automated Secret Filtering**: Ingestion skips files matching sensitive patterns including `.env*`, `*.pem`, `*.key`, `*id_rsa*`, `*.p12`, `*credentials*`, and `*.token`.
* **Ignored Build Directories**: Skips vendor and build directories (`node_modules`, `target`, `build`, `dist`, `.git`, `.idea`, `.vscode`, `__pycache__`).
* **Binary File Rejection**: Binary assets, archives (`.jar`, `.zip`), and compiled artifacts (`.class`, `.pyc`) are excluded from parsing.
* **Ephemeral Remote Clones**: Temporary GitHub clones are analyzed in memory or temporary directories and deleted via automated cleanup hooks (`finally` blocks).
* **Local Isolation**: SQLite storage and graph databases remain locally housed inside the `.ame/` workspace folder and are excluded from Git commits via `.gitignore`.

---

## Limitations

* **Static Analysis Boundaries**: Dynamic reflection, dynamic proxies, byte-code manipulation, and runtime dependency injection containers without compile-time bindings may not be fully resolved.
* **Language Support**: Production-grade AST parsing is currently implemented for **Java** (Spring/JPA) and **Python** (FastAPI/Flask/SQLAlchemy). Other languages are parsed via generic module/file nodes.
* **Distributed System Tracing**: Inter-service network communication across microservices is inferred from declarative API routes and event bindings; distributed trace verification requires runtime telemetry.
* **Benchmark Size**: Current benchmark numbers are measured against reference multi-tier architectures. Enterprise repositories with tens of thousands of classes will exhibit different graph density characteristics.

---

## Roadmap

- [x] Multi-source ingestion (Local Git, GitHub remote, live IDE streams)
- [x] Java AST parser (Spring controllers, services, repositories, JPA entities, JUnit)
- [x] Python AST parser (FastAPI routes, SQLAlchemy models, methods, pytest)
- [x] Hybrid SQLite persistent store + in-memory NetworkX traversal engine
- [x] Repository snapshot hierarchy (Commit, branch, and uncommitted workspace states)
- [x] Incremental AST diff updater
- [x] Structural change impact blast radius analyzer
- [x] Greedy relevance-per-token context optimizer
- [x] Model Context Protocol (MCP) stdio JSON-RPC server with 8 tools
- [x] FastAPI REST server with 11 endpoints
- [x] Cytoscape.js interactive graph visualizer with dynamic task query interface
- [x] Multi-task comparative evaluation suite (Full Context vs. Vector RAG vs. AME)
- [ ] TypeScript / JavaScript AST parser (React, Express, NestJS)
- [ ] Go AST parser (Goroutines, HTTP handlers, interfaces)
- [ ] Git commit log co-change statistical risk modeling
- [ ] OpenTelemetry distributed runtime trace ingestion
- [ ] Vector embedding hybrid reranking for large monolithic codebases

---

## Contributing

Contributions are welcome! To contribute:

1. **Fork** the repository on GitHub.
2. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Implement your change** and add corresponding unit tests under `tests/`.
4. **Run the test suite** to ensure all tests pass:
   ```bash
   python -m pytest tests/ -v
   ```
5. **Commit your changes**:
   ```bash
   git commit -m "Add feature: your feature description"
   ```
6. **Push to your fork and submit a Pull Request**.

---

## License

This project is licensed under the **Apache License 2.0**. See [`pyproject.toml`](file:///d:/antigravity_projects/Architecture%20Memory%20Engine/pyproject.toml) for package metadata.

---

## Project Status

* **Status**: Active Open-Source Engineering & AI Infrastructure Project
* **Maintained by**: AME Team
* **Repository**: [https://github.com/krupakargurije/Architecture-Memory-Engine](https://github.com/krupakargurije/Architecture-Memory-Engine)
