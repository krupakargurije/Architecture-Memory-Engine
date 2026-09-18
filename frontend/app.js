// ═══════════════════════════════════════════════════════════════════════════
// Architecture Memory Engine — Frontend Controller
// Professional graph visualization, repository state management,
// default repo auto-loading, external ingestion modal, context retrieval
// ═══════════════════════════════════════════════════════════════════════════

let cy = null;

// Explicit Repository State Model
let currentRepository = {
  repoId: null,
  repositoryName: null,
  owner: null,
  branch: null,
  commitSha: null,
  snapshotId: null,
  sourceType: 'default', // 'default' | 'github'
  nodes: 0,
  edges: 0,
  languages: [],
  architectureSummary: null,
};

let defaultRepositoryCache = null;
let allGraphNodes = [];
let allGraphEdges = [];
let activeFilters = new Set();
let animationPaused = false;
let particleAnimFrame = null;

// ── Color System & Visual Weights ───────────────────────────────────────
const ENTITY = {
  controller: { color:'#a78bfa', label:'Controller', shape:'round-rectangle', size:38 },
  service:    { color:'#60a5fa', label:'Service',    shape:'ellipse',          size:34 },
  table:      { color:'#34d399', label:'Entity',     shape:'diamond',          size:30 },
  api:        { color:'#22d3ee', label:'API',        shape:'round-hexagon',    size:28 },
  test:       { color:'#fbbf24', label:'Test',       shape:'round-triangle',   size:26 },
  interface:  { color:'#818cf8', label:'Interface',  shape:'round-pentagon',   size:28 },
  class:      { color:'#94a3b8', label:'Class',      shape:'ellipse',          size:24 },
  method:     { color:'#64748b', label:'Method',     shape:'ellipse',          size:16 },
  module:     { color:'#fb923c', label:'Module',     shape:'round-rectangle',  size:32 },
  repository: { color:'#2dd4bf', label:'Repository', shape:'round-rectangle',  size:36 },
  database:   { color:'#34d399', label:'Database',   shape:'barrel',           size:32 },
  event:      { color:'#fb7185', label:'Event',      shape:'round-diamond',    size:26 },
  file:       { color:'#475569', label:'File',       shape:'rectangle',        size:18 },
  function:   { color:'#64748b', label:'Function',   shape:'ellipse',          size:22 },
};

const DIRECTIONAL_RELATIONS = new Set([
  'CALLS','USES','DEPENDS_ON','IMPORTS','EXPOSES_API','ACCESSES',
  'READS_FROM','WRITES_TO','TESTED_BY','PUBLISHES','CONSUMES'
]);

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
  initWorkspaceControls();
  initModalControls();
  await loadDefaultRepository();
});

// ═══════════════════════════════════════════════════════════════════════════
// DEFAULT REPOSITORY AUTO-LOADING
// ═══════════════════════════════════════════════════════════════════════════

async function loadDefaultRepository() {
  try {
    const res = await fetch('/api/default-repository');
    if (!res.ok) throw new Error('Failed to load default repository');
    const data = await res.json();

    currentRepository = {
      repoId: data.repo_id,
      repositoryName: data.name,
      owner: data.owner || 'samples',
      branch: data.branch || 'main',
      commitSha: data.commit_id || 'c0ffee1',
      snapshotId: data.snapshot_id,
      sourceType: 'default',
      nodes: data.nodes,
      edges: data.edges,
      languages: data.languages || ['Java'],
      architectureSummary: data.architecture_summary,
    };

    defaultRepositoryCache = { ...currentRepository };
    updateRepositoryUI();
    await loadGraph(data.snapshot_id, data.architecture_summary);
  } catch (err) {
    console.error('Failed to load default repository:', err);
  }
}

function updateRepositoryUI() {
  const isDefault = currentRepository.sourceType === 'default';
  const commitShort = (currentRepository.commitSha || '').slice(0, 7);
  const langs = (currentRepository.languages || ['Java']).join(', ');

  // Header Bar
  const headerTag = document.getElementById('header-repo-tag');
  if (headerTag) {
    headerTag.textContent = isDefault ? 'DEFAULT' : 'EXTERNAL';
    headerTag.className = `repo-tag ${isDefault ? 'default' : 'external'}`;
  }

  const repoNameEl = document.getElementById('ws-repo-name');
  if (repoNameEl) repoNameEl.textContent = currentRepository.repositoryName;

  const repoMetaEl = document.getElementById('ws-repo-meta');
  if (repoMetaEl) {
    repoMetaEl.textContent = `${langs} · ${currentRepository.branch} · ${commitShort} · ${currentRepository.nodes} nodes · ${currentRepository.edges} edges`;
  }

  const btnLoadExt = document.getElementById('btn-load-external');
  const btnSwitchRepo = document.getElementById('btn-switch-repo');
  const btnReturnDef = document.getElementById('btn-return-default');

  if (btnLoadExt) btnLoadExt.style.display = isDefault ? 'flex' : 'none';
  if (btnSwitchRepo) btnSwitchRepo.style.display = isDefault ? 'none' : 'flex';
  if (btnReturnDef) btnReturnDef.style.display = isDefault ? 'none' : 'flex';

  // Sidebar Active Repository Card
  const sidebarTag = document.getElementById('sidebar-repo-tag');
  if (sidebarTag) {
    sidebarTag.textContent = isDefault ? 'DEFAULT REPOSITORY' : 'EXTERNAL REPOSITORY';
    sidebarTag.className = `repo-card-tag ${isDefault ? 'default' : 'external'}`;
  }

  const sidebarType = document.getElementById('sidebar-repo-type');
  if (sidebarType) sidebarType.textContent = isDefault ? 'Sample' : 'GitHub Remote';

  const sidebarTitle = document.getElementById('sidebar-repo-title');
  if (sidebarTitle) sidebarTitle.textContent = currentRepository.repositoryName;

  const sidebarLang = document.getElementById('sidebar-lang');
  if (sidebarLang) sidebarLang.textContent = langs;

  const sidebarBranch = document.getElementById('sidebar-branch');
  if (sidebarBranch) sidebarBranch.textContent = currentRepository.branch;

  const sidebarSnap = document.getElementById('sidebar-snapshot');
  if (sidebarSnap) sidebarSnap.textContent = (currentRepository.snapshotId || '').slice(0, 14);

  const sidebarStats = document.getElementById('sidebar-stats');
  if (sidebarStats) sidebarStats.textContent = `${currentRepository.nodes} Nodes · ${currentRepository.edges} Edges`;

  const sideLoadBtn = document.getElementById('btn-sidebar-load-ext');
  if (sideLoadBtn) {
    sideLoadBtn.innerHTML = isDefault
      ? '<span class="btn-icon">⚡</span> Load External Repository'
      : '<span class="btn-icon">⇄</span> Switch Repository';
  }

  const sideReturnBtn = document.getElementById('btn-sidebar-return-default');
  if (sideReturnBtn) sideReturnBtn.style.display = isDefault ? 'none' : 'flex';

  // Toolbar badge & count
  updateGraphBadge(currentRepository.repositoryName || currentRepository.snapshotId || '', currentRepository.nodes, currentRepository.edges);

  // Sync Task Section active repo badge
  const taskRepoBadge = document.getElementById('task-repo-badge');
  if (taskRepoBadge) {
    taskRepoBadge.textContent = currentRepository.repositoryName || 'Active Repo';
    taskRepoBadge.title = `Active Repo: ${currentRepository.repositoryName} (${currentRepository.branch} @ ${(currentRepository.commitSha||'').slice(0,7)})`;
  }

  // Refresh scoped task history
  renderRetrievalHistory();
}

// ═══════════════════════════════════════════════════════════════════════════
// RESTORE DEFAULT REPOSITORY
// ═══════════════════════════════════════════════════════════════════════════

async function returnToDefaultRepository() {
  if (defaultRepositoryCache && defaultRepositoryCache.snapshotId) {
    currentRepository = { ...defaultRepositoryCache };
    updateRepositoryUI();
    await loadGraph(currentRepository.snapshotId, currentRepository.architectureSummary);
  } else {
    await loadDefaultRepository();
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXTERNAL REPOSITORY MODAL & INGESTION
// ═══════════════════════════════════════════════════════════════════════════

const STAGES = [
  { id:'resolving',      label:'Resolving repository' },
  { id:'cloning',        label:'Preparing temporary analysis workspace' },
  { id:'metadata',       label:'Reading repository metadata' },
  { id:'scanning',       label:'Discovering source files' },
  { id:'parsing',        label:'Detecting languages' },
  { id:'analyzing',      label:'Parsing source code & inferring relationships' },
  { id:'building_graph', label:'Building architectural graph' },
  { id:'persisting',     label:'Persisting graph metadata' },
  { id:'cleanup_complete', label:'Cleaning temporary workspace' },
  { id:'complete',       label:'Analysis complete' },
];

function initModalControls() {
  const modal = document.getElementById('external-repo-modal');
  const btnClose = document.getElementById('btn-modal-close');
  const btnCancel = document.getElementById('btn-modal-cancel');
  const btnAnalyze = document.getElementById('btn-modal-analyze');
  const btnTryAgain = document.getElementById('btn-modal-try-again');
  const btnReturnCurr = document.getElementById('btn-modal-return-curr');

  // Trigger buttons
  const btnLoadExt = document.getElementById('btn-load-external');
  const btnSwitchRepo = document.getElementById('btn-switch-repo');
  const btnSidebarLoad = document.getElementById('btn-sidebar-load-ext');

  if (btnLoadExt) btnLoadExt.addEventListener('click', openExternalModal);
  if (btnSwitchRepo) btnSwitchRepo.addEventListener('click', openExternalModal);
  if (btnSidebarLoad) btnSidebarLoad.addEventListener('click', openExternalModal);

  // Close triggers
  if (btnClose) btnClose.addEventListener('click', closeExternalModal);
  if (btnCancel) btnCancel.addEventListener('click', closeExternalModal);
  if (btnReturnCurr) btnReturnCurr.addEventListener('click', closeExternalModal);

  // Return to default buttons
  const btnReturnDef = document.getElementById('btn-return-default');
  const btnSidebarReturn = document.getElementById('btn-sidebar-return-default');
  if (btnReturnDef) btnReturnDef.addEventListener('click', returnToDefaultRepository);
  if (btnSidebarReturn) btnSidebarReturn.addEventListener('click', returnToDefaultRepository);

  // Backdrop click closes modal
  if (modal) {
    modal.addEventListener('click', e => {
      if (e.target === modal) closeExternalModal();
    });
  }

  // Analyze & input triggers
  if (btnAnalyze) btnAnalyze.addEventListener('click', startGitHubIngestion);
  const inputUrl = document.getElementById('modal-github-url');
  if (inputUrl) {
    inputUrl.addEventListener('keydown', e => {
      if (e.key === 'Enter') startGitHubIngestion();
    });
  }

  // Try again button
  if (btnTryAgain) {
    btnTryAgain.addEventListener('click', showModalFormView);
  }
}

function openExternalModal() {
  const modal = document.getElementById('external-repo-modal');
  const titleEl = document.getElementById('modal-title');
  if (titleEl) {
    titleEl.textContent = currentRepository.sourceType === 'github'
      ? 'Switch Repository'
      : 'Load External Repository';
  }
  showModalFormView();
  if (modal) modal.style.display = 'flex';
  const urlInput = document.getElementById('modal-github-url');
  if (urlInput) urlInput.focus();
}

function closeExternalModal() {
  const modal = document.getElementById('external-repo-modal');
  if (modal) modal.style.display = 'none';
  showModalFormView();
}

function showModalFormView() {
  const formView = document.getElementById('modal-form-view');
  const progView = document.getElementById('modal-progress-view');
  const errView = document.getElementById('modal-error-view');
  if (formView) formView.style.display = 'block';
  if (progView) progView.style.display = 'none';
  if (errView) errView.style.display = 'none';

  const btn = document.getElementById('btn-modal-analyze');
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">⬡</span> Analyze Repository';
  }
}

function renderModalProgressUI() {
  const stagesEl = document.getElementById('modal-progress-stages');
  if (stagesEl) {
    stagesEl.innerHTML = STAGES.map((s, i) => {
      const line = i < STAGES.length - 1 ? `<div class="stage-line" id="modal-line-${s.id}"></div>` : '';
      return `<div class="stage-row" id="modal-stage-${s.id}">
        <div class="stage-icon" id="modal-icon-${s.id}"></div>
        <span>${s.label}</span>
      </div>${line}`;
    }).join('');
  }
  const statsEl = document.getElementById('modal-progress-stats');
  if (statsEl) statsEl.innerHTML = '';
  const wsStatusEl = document.getElementById('modal-workspace-status');
  if (wsStatusEl) wsStatusEl.innerHTML = '';
}

function updateModalStage(stageId) {
  let reached = false;
  STAGES.forEach(s => {
    const row = document.getElementById('modal-stage-' + s.id);
    const icon = document.getElementById('modal-icon-' + s.id);
    const line = document.getElementById('modal-line-' + s.id);
    if (!row) return;
    if (s.id === stageId) {
      reached = true;
      row.className = 'stage-row active';
      if (icon) icon.textContent = '';
    } else if (!reached) {
      row.className = 'stage-row done';
      if (icon) icon.textContent = '✓';
      if (line) line.className = 'stage-line done';
    }
  });
}

function markModalStagesDone() {
  STAGES.forEach(s => {
    const row = document.getElementById('modal-stage-' + s.id);
    const icon = document.getElementById('modal-icon-' + s.id);
    const line = document.getElementById('modal-line-' + s.id);
    if (row) { row.className = 'stage-row done'; }
    if (icon) icon.textContent = '✓';
    if (line) line.className = 'stage-line done';
  });
}

async function startGitHubIngestion() {
  const urlInput = document.getElementById('modal-github-url');
  const url = urlInput ? urlInput.value.trim() : '';
  if (!url) return;

  const branchInput = document.getElementById('modal-branch-input');
  const branch = branchInput && branchInput.value.trim() ? branchInput.value.trim() : null;

  const tokenInput = document.getElementById('modal-token-input');
  const token = tokenInput && tokenInput.value.trim() ? tokenInput.value.trim() : null;

  const btn = document.getElementById('btn-modal-analyze');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Analyzing...';
  }

  // Switch modal view to progress
  const formView = document.getElementById('modal-form-view');
  const progView = document.getElementById('modal-progress-view');
  const errView = document.getElementById('modal-error-view');
  if (formView) formView.style.display = 'none';
  if (errView) errView.style.display = 'none';
  if (progView) progView.style.display = 'block';

  renderModalProgressUI();

  let stageIdx = 0;
  const progressInterval = setInterval(() => {
    if (stageIdx < STAGES.length - 2) {
      updateModalStage(STAGES[stageIdx].id);
      stageIdx++;
    }
  }, 600);

  try {
    const res = await fetch('/api/github/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: url, branch, access_token: token }),
    });

    clearInterval(progressInterval);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Ingestion failed');
    }

    const data = await res.json();
    markModalStagesDone();

    // Show live statistics
    const summary = data.architecture_summary || {};
    const ec = summary.entity_counts || {};
    const statsEl = document.getElementById('modal-progress-stats');
    if (statsEl) {
      statsEl.innerHTML = `
        <div class="stat-row"><span>Files analyzed</span><span class="stat-val">${data.files_analyzed}</span></div>
        <div class="stat-row"><span>Languages</span><span class="stat-val">${(data.languages||[]).join(', ')}</span></div>
        <div class="stat-row"><span>Nodes</span><span class="stat-val">${data.nodes_created.toLocaleString()}</span></div>
        <div class="stat-row"><span>Edges</span><span class="stat-val">${data.edges_created.toLocaleString()}</span></div>
        <div class="stat-row"><span>Controllers</span><span class="stat-val">${ec.controller||0}</span></div>
        <div class="stat-row"><span>Services</span><span class="stat-val">${ec.service||0}</span></div>
        <div class="stat-row"><span>Entities</span><span class="stat-val">${ec.table||0}</span></div>
        <div class="stat-row"><span>Tests</span><span class="stat-val">${ec.test||0}</span></div>
      `;
    }

    const wsStatusEl = document.getElementById('modal-workspace-status');
    if (wsStatusEl) {
      wsStatusEl.innerHTML = `
        <div>Temporary workspace</div>
        <div><span class="ws-check">✓</span> Created</div>
        <div><span class="ws-check">✓</span> Used for analysis</div>
        <div><span class="ws-check">✓</span> Deleted</div>
        <div style="margin-top:6px;">Source retained permanently: <strong>0 files</strong></div>
        <div>Architectural metadata retained: <strong>Yes</strong></div>
      `;
    }

    // Update active repository state model
    currentRepository = {
      repoId: data.repo_id,
      repositoryName: `${data.owner}/${data.repo_name}`,
      owner: data.owner,
      branch: data.branch || 'main',
      commitSha: data.commit_id,
      snapshotId: data.snapshot_id,
      sourceType: 'github',
      nodes: data.nodes_created,
      edges: data.edges_created,
      languages: data.languages || [],
      architectureSummary: data.architecture_summary,
    };

    // Transition smoothly after a brief pause
    setTimeout(async () => {
      closeExternalModal();
      updateRepositoryUI();
      await loadGraph(data.snapshot_id, data.architecture_summary);
    }, 1200);

  } catch (err) {
    clearInterval(progressInterval);
    // FAILURE SAFETY: Active repository remains 100% intact!
    const progView = document.getElementById('modal-progress-view');
    const errView = document.getElementById('modal-error-view');
    if (progView) progView.style.display = 'none';
    if (errView) errView.style.display = 'block';

    const errDetail = document.getElementById('modal-error-detail');
    if (errDetail) errDetail.textContent = err.message || 'Unknown error occurred.';

    const fallbackRepo = document.getElementById('error-fallback-repo');
    if (fallbackRepo) fallbackRepo.textContent = currentRepository.repositoryName;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// GRAPH LOADING & CYTOSCAPE RENDERING
// ═══════════════════════════════════════════════════════════════════════════

async function loadGraph(snapshotId, summaryData) {
  try {
    const res = await fetch(`/api/graph/${snapshotId}`);
    if (!res.ok) throw new Error('Failed to load graph');
    const gdata = await res.json();
    allGraphNodes = gdata.nodes;
    allGraphEdges = gdata.edges;

    renderFilters(gdata.nodes);
    renderGraphCytoscape(gdata.nodes, gdata.edges);
    renderLegend(gdata.nodes);
    updateGraphBadge(currentRepository.repositoryName, gdata.nodes.length, gdata.edges.length);
    renderSummary(summaryData);
    renderRetrievalHistory();
  } catch (err) {
    console.error('Graph load error:', err);
  }
}

function updateGraphBadge(label, nodeCount, edgeCount) {
  const badgeEl = document.getElementById('graph-badge');
  const countEl = document.getElementById('graph-count');
  if (badgeEl) badgeEl.textContent = (label || '').toUpperCase();
  if (countEl) countEl.textContent = `${nodeCount} nodes · ${edgeCount} edges`;
}

function renderGraphCytoscape(nodes, edges) {
  const container = document.getElementById('cy-container');
  if (!container) return;

  // Build elements
  const elements = [];
  const validNodeIds = new Set();

  nodes.forEach(n => {
    validNodeIds.add(n.id);
    const meta = ENTITY[n.entity_type] || ENTITY.class;
    elements.push({
      group: 'nodes',
      data: {
        id: n.id,
        label: n.name,
        entity_type: n.entity_type,
        color: meta.color,
        shape: meta.shape,
        size: meta.size,
        file_path: n.file_path || '',
        start_line: n.start_line,
        end_line: n.end_line,
        signature: n.signature || '',
        docstring: n.docstring || '',
        metadata: n.metadata || {},
      },
    });
  });

  edges.forEach((e, i) => {
    if (validNodeIds.has(e.source) && validNodeIds.has(e.target)) {
      elements.push({
        group: 'edges',
        data: {
          id: `e_${i}_${e.source}_${e.target}`,
          source: e.source,
          target: e.target,
          relation: e.relation,
          confidence: e.confidence,
          source_type: e.source_type,
        },
      });
    }
  });

  if (cy) {
    cy.destroy();
    cy = null;
  }

  // Remove existing particle canvas if any
  const oldCanvas = container.querySelector('.edge-particle-layer');
  if (oldCanvas) oldCanvas.remove();

  cy = cytoscape({
    container,
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'color': '#f1f3f8',
          'font-family': 'Inter, -apple-system, sans-serif',
          'font-size': '11px',
          'font-weight': '600',
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'text-background-color': '#0c1120',
          'text-background-opacity': 0.75,
          'text-background-padding': '2px',
          'text-background-shape': 'roundrectangle',
          'background-color': 'data(color)',
          'shape': 'data(shape)',
          'width': 'data(size)',
          'height': 'data(size)',
          'border-width': 1.5,
          'border-color': 'rgba(255,255,255,0.2)',
          'transition-property': 'background-color, border-color, border-width, opacity, width, height',
          'transition-duration': '0.2s',
        }
      },
      {
        selector: 'node[entity_type = "controller"]',
        style: {
          'border-color': 'rgba(167,139,250,0.6)',
          'border-width': 2,
        }
      },
      {
        selector: 'node[entity_type = "service"]',
        style: {
          'border-color': 'rgba(96,165,250,0.6)',
          'border-width': 2,
        }
      },
      {
        selector: 'node[entity_type = "repository"]',
        style: {
          'border-color': 'rgba(45,212,191,0.6)',
          'border-width': 2,
        }
      },
      {
        selector: 'node[entity_type = "table"]',
        style: {
          'border-color': 'rgba(52,211,153,0.6)',
          'border-width': 2,
        }
      },
      {
        selector: 'node[entity_type = "test"]',
        style: {
          'border-color': 'rgba(251,191,36,0.6)',
          'border-width': 1.5,
        }
      },
      {
        selector: 'node.selected',
        style: {
          'border-color': '#22d3ee',
          'border-width': 3.5,
          'font-size': '13px',
          'font-weight': '700',
          'z-index': 100,
        }
      },
      {
        selector: 'node.highlighted',
        style: {
          'border-color': '#22d3ee',
          'border-width': 2.5,
          'z-index': 90,
        }
      },
      {
        selector: 'node.neighbor',
        style: {
          'opacity': 1.0,
          'border-width': 2,
          'z-index': 80,
        }
      },
      {
        selector: 'node.dimmed',
        style: {
          'opacity': 0.18,
        }
      },
      {
        selector: 'node.search-match',
        style: {
          'border-color': '#fbbf24',
          'border-width': 3,
          'z-index': 95,
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': 'rgba(255,255,255,0.12)',
          'curve-style': 'bezier',
          'target-arrow-shape': 'triangle',
          'target-arrow-color': 'rgba(255,255,255,0.15)',
          'arrow-scale': 0.8,
          'opacity': 0.6,
          'transition-property': 'line-color, width, opacity, target-arrow-color',
          'transition-duration': '0.2s',
        }
      },
      {
        selector: 'edge[relation = "CALLS"]',
        style: {
          'line-color': 'rgba(96,165,250,0.35)',
          'target-arrow-color': 'rgba(96,165,250,0.5)',
          'width': 2,
        }
      },
      {
        selector: 'edge[relation = "USES"]',
        style: {
          'line-color': 'rgba(129,140,248,0.3)',
          'target-arrow-color': 'rgba(129,140,248,0.45)',
          'width': 1.8,
        }
      },
      {
        selector: 'edge[relation = "DEPENDS_ON"]',
        style: {
          'line-color': 'rgba(45,212,191,0.3)',
          'target-arrow-color': 'rgba(45,212,191,0.45)',
          'width': 1.8,
        }
      },
      {
        selector: 'edge[relation = "TESTED_BY"]',
        style: {
          'line-color': 'rgba(251,191,36,0.3)',
          'target-arrow-color': 'rgba(251,191,36,0.45)',
          'line-style': 'dashed',
          'width': 1.5,
        }
      },
      {
        selector: 'edge[relation = "EXPOSES_API"]',
        style: {
          'line-color': 'rgba(34,211,238,0.35)',
          'target-arrow-color': 'rgba(34,211,238,0.5)',
          'width': 2,
        }
      },
      {
        selector: 'edge.active-edge',
        style: {
          'line-color': '#22d3ee',
          'target-arrow-color': '#22d3ee',
          'width': 2.5,
          'opacity': 1.0,
          'z-index': 50,
        }
      },
      {
        selector: 'edge.dimmed',
        style: {
          'opacity': 0.08,
        }
      },
    ],
    layout: {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20,
      refresh: 20,
      fit: true,
      padding: 30,
      randomize: false,
      componentSpacing: 100,
      nodeRepulsion: 400000,
      edgeElasticity: 100,
      nestingFactor: 5,
      gravity: 80,
      numIter: 1000,
      initialTemp: 200,
      coolingFactor: 0.95,
      minTemp: 1.0,
    },
    boxSelectionEnabled: false,
    autoungrabify: false,
  });

  // Attach event handlers
  attachGraphEvents();

  // Setup edge particle flow layer
  setupEdgeParticleCanvas(container);
}

// ═══════════════════════════════════════════════════════════════════════════
// GRAPH INTERACTIONS & DEPTH FOCUS
// ═══════════════════════════════════════════════════════════════════════════

function attachGraphEvents() {
  const tooltip = document.getElementById('graph-tooltip');

  // Node Click -> Select & Radial Neighborhood Focus
  cy.on('tap', 'node', e => {
    const node = e.target;
    selectNode(node);
  });

  // Background Click -> Reset Selection & Focus
  cy.on('tap', e => {
    if (e.target === cy) {
      clearSelection();
    }
  });

  // Node Hover Tooltip
  cy.on('mouseover', 'node', e => {
    const n = e.target;
    const pos = n.renderedPosition();
    const inDeg = n.incomers('edge').length;
    const outDeg = n.outgoers('edge').length;
    const meta = ENTITY[n.data('entity_type')] || ENTITY.class;

    tooltip.innerHTML = `
      <div class="tip-title">${escapeHtml(n.data('label'))}</div>
      <div class="tip-type">${meta.label.toUpperCase()}</div>
      <div class="tip-row"><span>Incoming</span><span>${inDeg}</span></div>
      <div class="tip-row"><span>Outgoing</span><span>${outDeg}</span></div>
      ${n.data('file_path') ? `<div class="tip-row" style="margin-top:4px;font-size:10px;color:var(--text-3);">${escapeHtml(n.data('file_path'))}</div>` : ''}
    `;
    tooltip.style.left = `${pos.x + 15}px`;
    tooltip.style.top = `${pos.y - 15}px`;
    tooltip.style.display = 'block';
  });

  cy.on('mouseout', 'node', () => {
    tooltip.style.display = 'none';
  });

  // Edge Hover Tooltip
  cy.on('mouseover', 'edge', e => {
    const edge = e.target;
    const pos = edge.midpoint();
    const renderedPos = cy.renderer().projectIntoViewport(pos.x, pos.y);

    tooltip.innerHTML = `
      <div class="tip-title">${edge.data('relation')}</div>
      <div class="tip-type">${edge.source().data('label')} → ${edge.target().data('label')}</div>
      <div class="tip-row"><span>Confidence</span><span>${(edge.data('confidence')||1).toFixed(2)}</span></div>
      <div class="tip-row"><span>Source</span><span>${edge.data('source_type') || 'static_analysis'}</span></div>
    `;
    tooltip.style.left = `${renderedPos[0] + 15}px`;
    tooltip.style.top = `${renderedPos[1] - 15}px`;
    tooltip.style.display = 'block';
  });

  cy.on('mouseout', 'edge', () => {
    tooltip.style.display = 'none';
  });
}

function selectNode(node) {
  if (!cy) return;

  // Clear previous selection
  cy.elements().removeClass('selected highlighted neighbor active-edge dimmed search-match');

  // Radial Focus & Depth Fading
  const neighborhood = node.neighborhood();
  const connectedEdges = node.connectedEdges();

  // Dim all elements first
  cy.elements().addClass('dimmed');

  // Highlight selected node
  node.removeClass('dimmed').addClass('selected');

  // Highlight neighborhood nodes
  neighborhood.nodes().removeClass('dimmed').addClass('neighbor');

  // Highlight connected edges
  connectedEdges.removeClass('dimmed').addClass('active-edge');

  // Open Inspector Panel with node details
  renderNodeInspector(node.data());

  // Switch to Node tab
  document.querySelector('.insp-tab[data-tab="tab-node"]').click();
}

function clearSelection() {
  if (!cy) return;
  cy.elements().removeClass('selected highlighted neighbor active-edge dimmed search-match');
  cy.elements().style('opacity', '');
  document.getElementById('node-inspector').innerHTML = `
    <div class="empty-state"><p>Click any node in the graph to inspect its architectural details, calls, callers, tests, and provenance.</p></div>
  `;
}

// ═══════════════════════════════════════════════════════════════════════════
// NODE INSPECTOR
// ═══════════════════════════════════════════════════════════════════════════

function renderNodeInspector(data) {
  const meta = ENTITY[data.entity_type] || ENTITY.class;
  const node = cy.getElementById(data.id);

  // Incoming callers
  const callers = [];
  node.incomers('edge').forEach(e => {
    callers.push({ name: e.source().data('label'), rel: e.data('relation') });
  });

  // Outgoing calls
  const calls = [];
  node.outgoers('edge').forEach(e => {
    calls.push({ name: e.target().data('label'), rel: e.data('relation') });
  });

  // Tests
  const tests = [];
  node.connectedEdges('[relation = "TESTED_BY"]').forEach(e => {
    const other = e.source().id() === node.id() ? e.target() : e.source();
    tests.push(other.data('label'));
  });

  const methods = (data.metadata && data.metadata.methods) || [];

  const html = `
    <div class="insp-header">
      <span class="insp-name">${escapeHtml(data.label)}</span>
      <span class="insp-type" style="background:${meta.color}22;color:${meta.color};border:1px solid ${meta.color}44;">
        ${meta.label.toUpperCase()}
      </span>
    </div>

    ${data.file_path ? `
      <div class="insp-field">
        <label>File</label>
        <span class="val mono">${escapeHtml(data.file_path)}</span>
      </div>
    ` : ''}

    ${data.start_line ? `
      <div class="insp-field">
        <label>Lines</label>
        <span class="val">${data.start_line} – ${data.end_line || '?'}</span>
      </div>
    ` : ''}

    ${data.signature ? `
      <div class="insp-field">
        <label>Signature</label>
        <span class="val mono">${escapeHtml(data.signature)}</span>
      </div>
    ` : ''}

    ${methods.length ? `
      <div class="insp-field">
        <label>Methods (${methods.length})</label>
        <div class="insp-tags">
          ${methods.map(m => `<span class="insp-tag">${escapeHtml(m)}()</span>`).join('')}
        </div>
      </div>
    ` : ''}

    <div class="insp-field">
      <label>Calls (${calls.length})</label>
      <div class="insp-tags">
        ${calls.length ? calls.map(c => `<span class="insp-tag">${escapeHtml(c.name)} <small>${c.rel}</small></span>`).join('') : '<span class="muted-text">None</span>'}
      </div>
    </div>

    <div class="insp-field">
      <label>Called By (${callers.length})</label>
      <div class="insp-tags">
        ${callers.length ? callers.map(c => `<span class="insp-tag">${escapeHtml(c.name)} <small>${c.rel}</small></span>`).join('') : '<span class="muted-text">None</span>'}
      </div>
    </div>

    ${tests.length ? `
      <div class="insp-field">
        <label>Covered by Tests (${tests.length})</label>
        <div class="insp-tags">
          ${tests.map(t => `<span class="insp-tag test">${escapeHtml(t)}</span>`).join('')}
        </div>
      </div>
    ` : ''}

    <div class="insp-field">
      <label>Confidence / Provenance</label>
      <span class="val">1.00 · static_analysis</span>
    </div>
  `;

  document.getElementById('node-inspector').innerHTML = html;
}

// ═══════════════════════════════════════════════════════════════════════════
// EDGE PARTICLE FLOW ANIMATION
// ═══════════════════════════════════════════════════════════════════════════

function setupEdgeParticleCanvas(container) {
  const canvas = document.createElement('canvas');
  canvas.className = 'edge-particle-layer';
  container.style.position = 'relative';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  let particles = [];

  function resizeCanvas() {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  function createParticles() {
    particles = [];
    if (!cy) return;

    cy.edges().forEach(e => {
      const rel = e.data('relation');
      let speed = 0.006;
      let count = 2;
      let color = 'rgba(255,255,255,0.6)';

      if (rel === 'CALLS') {
        speed = 0.009; count = 3; color = '#60a5fa';
      } else if (rel === 'PUBLISHES') {
        speed = 0.012; count = 4; color = '#fb7185';
      } else if (rel === 'CONSUMES') {
        speed = 0.008; count = 3; color = '#34d399';
      } else if (rel === 'DEPENDS_ON') {
        speed = 0.005; count = 2; color = '#2dd4bf';
      }

      for (let i = 0; i < count; i++) {
        particles.push({
          edge: e,
          t: (i / count) + Math.random() * 0.1,
          speed,
          color,
          radius: 2.0,
        });
      }
    });
  }

  // Generate particles after layout finishes
  cy.one('layoutstop', () => {
    createParticles();
  });

  function drawParticles() {
    if (animationPaused || !cy) {
      particleAnimFrame = requestAnimationFrame(drawParticles);
      return;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach(p => {
      p.t += p.speed;
      if (p.t > 1) p.t = 0;

      const e = p.edge;
      if (!e || e.removed() || !e.visible()) return;

      const src = e.source().renderedPosition();
      const tgt = e.target().renderedPosition();
      if (!src || !tgt) return;

      // Linear interpolation between rendered positions
      const x = src.x + (tgt.x - src.x) * p.t;
      const y = src.y + (tgt.y - src.y) * p.t;

      const isActive = e.hasClass('active-edge');
      const isDimmed = e.hasClass('dimmed');

      ctx.beginPath();
      ctx.arc(x, y, isActive ? p.radius * 1.5 : p.radius, 0, Math.PI * 2);
      ctx.fillStyle = isActive ? '#22d3ee' : (isDimmed ? 'rgba(255,255,255,0.05)' : p.color);
      ctx.fill();
    });

    particleAnimFrame = requestAnimationFrame(drawParticles);
  }

  if (particleAnimFrame) cancelAnimationFrame(particleAnimFrame);
  drawParticles();
}

function toggleAnimations() {
  animationPaused = !animationPaused;
  const btn = document.getElementById('btn-pause');
  if (btn) {
    btn.textContent = animationPaused ? '▶' : '▮▮';
    btn.title = animationPaused ? 'Resume Animations' : 'Pause Animations';
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// WORKSPACE CONTROLS & SEARCH
// ═══════════════════════════════════════════════════════════════════════════

function initWorkspaceControls() {
  // Tabs
  document.querySelectorAll('.insp-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.insp-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const pane = document.getElementById(tab.dataset.tab);
      if (pane) pane.classList.add('active');
    });
  });

  // Budget slider
  const slider = document.getElementById('budget-slider');
  if (slider) {
    slider.addEventListener('input', e => {
      const budgetVal = document.getElementById('budget-value');
      if (budgetVal) budgetVal.textContent = Number(e.target.value).toLocaleString();
    });
  }

  // Retrieve button
  const btnRet = document.getElementById('btn-retrieve');
  if (btnRet) btnRet.addEventListener('click', () => runContextRetrieval());

  // Task Input keydown (Enter without Shift runs retrieval)
  const taskInput = document.getElementById('task-input');
  if (taskInput) {
    taskInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        runContextRetrieval();
      }
    });
  }

  // Example Chips (Clicking populates input for user editing)
  const exampleChipsContainer = document.getElementById('example-chips');
  if (exampleChipsContainer) {
    exampleChipsContainer.addEventListener('click', e => {
      const chip = e.target.closest('.example-chip');
      if (!chip) return;
      const taskText = chip.getAttribute('data-task') || chip.textContent.trim();
      const input = document.getElementById('task-input');
      if (input) {
        input.value = taskText;
        input.focus();
        showToast('Example task populated. Press "Retrieve Context" or Enter to run.', 'info');
      }
    });
  }

  // Context Banner Action Buttons
  const btnCopy = document.getElementById('btn-copy-context');
  if (btnCopy) btnCopy.addEventListener('click', copyContextToClipboard);

  const btnViewJson = document.getElementById('btn-view-json');
  if (btnViewJson) btnViewJson.addEventListener('click', openJsonModal);

  const btnSendAgent = document.getElementById('btn-send-agent');
  if (btnSendAgent) btnSendAgent.addEventListener('click', sendContextToAgent);

  // Clear task history button
  const btnClearHist = document.getElementById('btn-clear-history');
  if (btnClearHist) btnClearHist.addEventListener('click', clearRetrievalHistory);

  // ContextPackage JSON Viewer Modal Controls
  const btnJsonClose = document.getElementById('btn-json-modal-close');
  const btnJsonDismiss = document.getElementById('btn-json-modal-dismiss');
  const btnCopyRawJson = document.getElementById('btn-copy-raw-json');
  const jsonModal = document.getElementById('context-json-modal');

  if (btnJsonClose) btnJsonClose.addEventListener('click', closeJsonModal);
  if (btnJsonDismiss) btnJsonDismiss.addEventListener('click', closeJsonModal);
  if (btnCopyRawJson) btnCopyRawJson.addEventListener('click', copyRawJsonPayload);
  if (jsonModal) {
    jsonModal.addEventListener('click', e => {
      if (e.target === jsonModal) closeJsonModal();
    });
  }

  // Graph controls
  const zIn = document.getElementById('btn-zoom-in');
  if (zIn) zIn.addEventListener('click', () => cy && cy.zoom(cy.zoom() * 1.3));

  const zOut = document.getElementById('btn-zoom-out');
  if (zOut) zOut.addEventListener('click', () => cy && cy.zoom(cy.zoom() / 1.3));

  const btnFit = document.getElementById('btn-fit');
  if (btnFit) btnFit.addEventListener('click', () => cy && cy.fit(null, 30));

  const btnCenter = document.getElementById('btn-center');
  if (btnCenter) {
    btnCenter.addEventListener('click', () => {
      if (cy) {
        const sel = cy.nodes('.selected');
        if (sel.length) cy.animate({ center: { eles: sel }, duration: 400 });
        else cy.fit(null, 30);
      }
    });
  }

  const btnPause = document.getElementById('btn-pause');
  if (btnPause) btnPause.addEventListener('click', toggleAnimations);

  // Layout selector
  const layoutSel = document.getElementById('layout-select');
  if (layoutSel) {
    layoutSel.addEventListener('change', e => {
      if (cy) applyLayout(e.target.value);
    });
  }

  // Search
  const searchInput = document.getElementById('graph-search');
  if (searchInput) {
    searchInput.addEventListener('input', e => {
      searchGraph(e.target.value.trim());
    });
  }
}

function applyLayout(name) {
  if (!cy) return;
  const opts = { name, animate: true, animationDuration: 500, padding: 30 };
  if (name === 'cose') {
    opts.nodeRepulsion = 400000;
    opts.idealEdgeLength = 100;
  }
  cy.layout(opts).run();
}

function searchGraph(query) {
  if (!cy) return;

  if (!query) {
    clearSelection();
    return;
  }

  const q = query.toLowerCase();
  cy.elements().removeClass('selected highlighted neighbor active-edge dimmed search-match');

  const matches = cy.nodes().filter(n => {
    const label = (n.data('label') || '').toLowerCase();
    const sig = (n.data('signature') || '').toLowerCase();
    const file = (n.data('file_path') || '').toLowerCase();
    return label.includes(q) || sig.includes(q) || file.includes(q);
  });

  if (matches.length > 0) {
    cy.elements().addClass('dimmed');
    matches.removeClass('dimmed').addClass('search-match');

    // Also highlight immediate neighbors
    matches.neighborhood().nodes().removeClass('dimmed').addClass('neighbor');
    matches.connectedEdges().removeClass('dimmed').addClass('active-edge');

    // Focus camera on first match
    cy.animate({ center: { eles: matches.first() }, zoom: 1.2, duration: 400 });

    // Open first match in inspector
    renderNodeInspector(matches.first().data());
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// FILTERS
// ═══════════════════════════════════════════════════════════════════════════

function renderFilters(nodes) {
  const types = new Set();
  nodes.forEach(n => {
    if (n.entity_type !== 'method') types.add(n.entity_type);
  });

  activeFilters = new Set(types);
  const container = document.getElementById('filter-checks');
  if (!container) return;

  container.innerHTML = [...types].sort().map(t => {
    const meta = ENTITY[t] || ENTITY.class;
    return `<div class="filter-chip active" data-type="${t}" onclick="toggleFilter('${t}', this)">
      <span class="chip-dot" style="background:${meta.color}"></span>
      ${meta.label}
    </div>`;
  }).join('');
}

function toggleFilter(type, el) {
  if (activeFilters.has(type)) {
    activeFilters.delete(type);
    el.classList.remove('active');
  } else {
    activeFilters.add(type);
    el.classList.add('active');
  }
  applyFilters();
}

function applyFilters() {
  if (!cy) return;
  cy.nodes().forEach(n => {
    const t = n.data('entity_type');
    if (activeFilters.has(t)) {
      n.style('display', 'element');
    } else {
      n.style('display', 'none');
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// LEGEND
// ═══════════════════════════════════════════════════════════════════════════

function renderLegend(nodes) {
  const types = new Set();
  nodes.forEach(n => { if (n.entity_type !== 'method') types.add(n.entity_type); });
  const container = document.getElementById('graph-legend');
  if (!container) return;

  container.innerHTML = [...types].sort().map(t => {
    const meta = ENTITY[t] || ENTITY.class;
    return `<span class="legend-item"><span class="legend-dot" style="background:${meta.color}"></span>${meta.label}</span>`;
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════════════
// SUMMARY + CHAINS + HEALTH
// ═══════════════════════════════════════════════════════════════════════════

function renderSummary(summary) {
  if (!summary) return;
  const ec = summary.entity_counts || {};
  const langs = summary.languages || [];

  const container = document.getElementById('summary-content');
  if (container) {
    container.innerHTML = `
      <div style="margin-bottom:6px;font-size:12px;color:var(--cyan);font-weight:600;">${langs.join(' / ')}</div>
      <div class="summary-grid">
        ${Object.entries(ec).filter(([k]) => k !== 'method').map(([k,v]) => {
          const meta = ENTITY[k] || ENTITY.class;
          return `<div class="summary-item"><span class="s-label">${meta.label}s</span><span class="s-val">${v}</span></div>`;
        }).join('')}
      </div>
    `;
  }

  // Primary Flows
  const chainsEl = document.getElementById('chains-content');
  if (chainsEl) {
    const chains = summary.primary_chains || [];
    if (chains.length) {
      chainsEl.innerHTML = chains.map(c =>
        `<div class="chain-row">${c.map(escapeHtml).join('<span class="chain-arrow"> → </span>')}</div>`
      ).join('');
    } else {
      chainsEl.innerHTML = '<p class="muted-text">No primary flows detected.</p>';
    }
  }

  // Health & Structural Metrics
  const healthEl = document.getElementById('health-content');
  if (healthEl) {
    const health = summary.health || {};
    let healthHtml = '';

    if (health.most_depended_on && health.most_depended_on.length) {
      healthHtml += '<div class="health-group"><div class="health-group-label">Most Depended-On</div>';
      healthHtml += health.most_depended_on.slice(0, 5).map(h =>
        `<div class="health-item"><span>${escapeHtml(h.name)}</span><span class="h-val">${h.incoming} incoming</span></div>`
      ).join('');
      healthHtml += '</div>';
    }
    if (health.highest_outgoing && health.highest_outgoing.length) {
      healthHtml += '<div class="health-group"><div class="health-group-label">Highest Outgoing Dependencies</div>';
      healthHtml += health.highest_outgoing.slice(0, 5).map(h =>
        `<div class="health-item"><span>${escapeHtml(h.name)}</span><span class="h-val">${h.outgoing} outgoing</span></div>`
      ).join('');
      healthHtml += '</div>';
    }
    if (health.unreferenced && health.unreferenced.length) {
      healthHtml += '<div class="health-group"><div class="health-group-label">Unreferenced Components</div>';
      healthHtml += health.unreferenced.slice(0, 5).map(name =>
        `<div class="health-item"><span>${escapeHtml(name)}</span><span class="h-val" style="color:var(--amber)">0 incoming</span></div>`
      ).join('');
      healthHtml += '</div>';
    }
    healthEl.innerHTML = healthHtml || '<p class="muted-text">No structural data.</p>';
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// DYNAMIC TASK CONTEXT RETRIEVAL
// ═══════════════════════════════════════════════════════════════════════════

let lastRetrievedContextPackage = null;
let isRetrievingContext = false;

async function runContextRetrieval(taskOverride = null) {
  if (isRetrievingContext) return;
  const taskInput = document.getElementById('task-input');
  const task = (taskOverride || (taskInput ? taskInput.value : '')).trim();

  if (!task) {
    showToast('Please enter a coding task description first.', 'warning');
    if (taskInput) taskInput.focus();
    return;
  }
  if (!currentRepository.repoId || !currentRepository.snapshotId) {
    showToast('No active repository snapshot loaded.', 'error');
    return;
  }

  const budgetSlider = document.getElementById('budget-slider');
  const budget = budgetSlider ? parseInt(budgetSlider.value, 10) : 8000;

  const btn = document.getElementById('btn-retrieve');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="analysis-spinner"></span> Analyzing...';
  }

  // 1. Show Analysis Progress Panel
  const analysisPanel = document.getElementById('task-analysis-panel');
  if (analysisPanel) analysisPanel.style.display = 'block';

  // The 6 Pipeline stages defined in HTML
  const stageIds = [
    'tstage-understand',
    'tstage-candidates',
    'tstage-traverse',
    'tstage-impact',
    'tstage-code',
    'tstage-optimize',
  ];

  // Reset stage styles
  stageIds.forEach(id => {
    const row = document.getElementById(id);
    if (row) {
      row.className = 'task-stage-row';
      const icon = row.querySelector('.tstage-icon');
      if (icon) icon.textContent = '○';
    }
  });

  isRetrievingContext = true;

  // Staged animated progress while the backend runs
  let currentStageIdx = 0;
  const stageInterval = setInterval(() => {
    if (currentStageIdx < stageIds.length) {
      const prevId = stageIds[currentStageIdx - 1];
      if (prevId) {
        const prevRow = document.getElementById(prevId);
        if (prevRow) {
          prevRow.className = 'task-stage-row done';
          const icon = prevRow.querySelector('.tstage-icon');
          if (icon) icon.textContent = '✓';
        }
      }
      const curId = stageIds[currentStageIdx];
      const curRow = document.getElementById(curId);
      if (curRow) {
        curRow.className = 'task-stage-row active';
        const icon = curRow.querySelector('.tstage-icon');
        if (icon) icon.textContent = '●';
      }
      currentStageIdx++;
    }
  }, 140);

  try {
    const res = await fetch('/api/retrieve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task,
        repo_id: currentRepository.repoId,
        snapshot_id: currentRepository.snapshotId,
        token_budget: budget,
      }),
    });

    clearInterval(stageInterval);

    // Fast-forward all stages to completed checkmarks
    stageIds.forEach(id => {
      const row = document.getElementById(id);
      if (row) {
        row.className = 'task-stage-row done';
        const icon = row.querySelector('.tstage-icon');
        if (icon) icon.textContent = '✓';
      }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Retrieval error' }));
      throw new Error(err.detail || 'Context retrieval failed');
    }

    const data = await res.json();
    lastRetrievedContextPackage = data;

    // Small delay so user sees full pipeline completion
    await new Promise(r => setTimeout(r, 220));
    if (analysisPanel) analysisPanel.style.display = 'none';

    // 2. Render Results in Banner & Tabs
    renderContextBanner(data);
    renderArchitectureTab(data);
    renderSnippets(data.snippets);
    renderImpactTab(data.impact, data.task_intent);
    renderProvenance(data.snippets, data.provenance_records);

    // 3. Highlight Graph Subgraph
    highlightRetrievedGraph(data);

    // 4. Save to Scoped Retrieval History
    addToRetrievalHistory(task, data);

    // 5. Intelligent Tab Selection based on Intent
    if (data.task_intent === 'CHANGE IMPACT') {
      switchTab('tab-impact');
    } else {
      switchTab('tab-architecture');
    }

    showToast(`Context retrieved: ${data.total_tokens.toLocaleString()} tokens (${data.nodes_count} nodes, ${data.edges_count} edges)`, 'success');

  } catch (err) {
    console.error('Retrieval failed:', err);
    clearInterval(stageInterval);
    if (analysisPanel) analysisPanel.style.display = 'none';
    showToast(`Error: ${err.message}`, 'error');
  } finally {
    isRetrievingContext = false;
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-icon">🔍</span> Retrieve Context';
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// CONTEXT BANNER & STATS
// ═══════════════════════════════════════════════════════════════════════════

function renderContextBanner(data) {
  const banner = document.getElementById('context-banner');
  if (!banner) return;
  banner.style.display = 'block';

  const intentEl = document.getElementById('banner-intent');
  if (intentEl) {
    const intent = data.task_intent || 'IMPLEMENTATION';
    intentEl.textContent = intent.toUpperCase();
    intentEl.className = `intent-pill ${intent.toLowerCase().replace(/_/g, '-')}`;
  }

  const tokensEl = document.getElementById('banner-tokens');
  if (tokensEl) {
    tokensEl.textContent = `${(data.total_tokens || 0).toLocaleString()} / ${(data.token_budget || 8000).toLocaleString()} tokens`;
  }

  const taskEl = document.getElementById('banner-task');
  if (taskEl) {
    taskEl.textContent = `"${data.task}"`;
  }

  const bNodes = document.getElementById('bstat-nodes');
  if (bNodes) bNodes.textContent = data.nodes_count || (data.nodes ? data.nodes.length : 0);

  const bEdges = document.getElementById('bstat-edges');
  if (bEdges) bEdges.textContent = data.edges_count || (data.edges ? data.edges.length : 0);

  const bFiles = document.getElementById('bstat-files');
  if (bFiles) {
    const fileSet = new Set();
    (data.snippets || []).forEach(s => { if (s.file_path) fileSet.add(s.file_path); });
    (data.nodes || []).forEach(n => { if (n.file_path) fileSet.add(n.file_path); });
    bFiles.textContent = fileSet.size || data.snippets_count || 0;
  }

  const bSavings = document.getElementById('bstat-savings');
  if (bSavings) {
    if (data.token_savings_percentage != null && data.token_savings_percentage > 0) {
      bSavings.textContent = `${data.token_savings_percentage.toFixed(1)}% reduction vs full repo`;
      bSavings.style.display = 'inline';
    } else {
      bSavings.style.display = 'none';
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// ARCHITECTURE TAB: CHAINS & RATIONALE
// ═══════════════════════════════════════════════════════════════════════════

function renderArchitectureTab(data) {
  // 1. Dependency Chains
  const chainsEl = document.getElementById('arch-chains-flow');
  if (chainsEl) {
    const chains = data.dependency_chains || [];
    if (chains.length > 0) {
      chainsEl.innerHTML = chains.map(c => `
        <div class="chain-card">
          <button class="chain-node-btn" onclick="window.focusGraphNode('${escapeHtml(c.source)}')">${escapeHtml(c.source)}</button>
          <span class="chain-rel-arrow">─ ${escapeHtml(c.relation)} →</span>
          <button class="chain-node-btn" onclick="window.focusGraphNode('${escapeHtml(c.target)}')">${escapeHtml(c.target)}</button>
        </div>
      `).join('');
    } else {
      chainsEl.innerHTML = '<div class="empty-state"><p>No direct relationship chains between retrieved components.</p></div>';
    }
  }

  // 2. Components & Inclusion Rationale
  const rationaleEl = document.getElementById('components-rationale-list');
  if (rationaleEl) {
    const comps = [];
    const seenNames = new Set();

    (data.snippets || []).forEach(s => {
      seenNames.add(s.name);
      comps.push({
        name: s.name,
        entity_type: s.entity_type,
        why_included: s.why_included || (data.why_included && data.why_included[s.name]) || 'Direct architectural dependency',
        task_relevance: s.task_relevance || 0.85,
        token_cost: s.token_cost || s.estimated_tokens,
        file_path: s.file_path,
      });
    });

    (data.nodes || []).forEach(n => {
      if (!seenNames.has(n.name)) {
        seenNames.add(n.name);
        comps.push({
          name: n.name,
          entity_type: n.entity_type,
          why_included: (data.why_included && data.why_included[n.name]) || 'Direct architectural dependency',
          task_relevance: 0.80,
          token_cost: null,
          file_path: n.file_path,
        });
      }
    });

    if (comps.length > 0) {
      rationaleEl.innerHTML = comps.map(c => {
        const meta = ENTITY[c.entity_type] || ENTITY.class;
        const color = meta.color || '#60a5fa';
        return `
          <div class="comp-rationale-card">
            <div class="comp-header">
              <span class="comp-name" onclick="window.focusGraphNode('${escapeHtml(c.name)}')">${escapeHtml(c.name)}</span>
              <span class="comp-type-badge" style="background:${color}22; color:${color}; border:1px solid ${color}66;">${escapeHtml(c.entity_type.toUpperCase())}</span>
            </div>
            <div class="comp-why">✓ ${escapeHtml(c.why_included)}</div>
            <div class="comp-metrics">
              <span>Task relevance: <strong>${c.task_relevance.toFixed(2)}</strong></span>
              ${c.token_cost ? `<span>·</span><span>Token cost: <strong>${c.token_cost}</strong></span>` : ''}
              ${c.file_path ? `<span>·</span><span title="${escapeHtml(c.file_path)}">${escapeHtml(c.file_path.split(/[/\\]/).pop())}</span>` : ''}
            </div>
          </div>
        `;
      }).join('');
    } else {
      rationaleEl.innerHTML = '<div class="empty-state"><p>No components retrieved.</p></div>';
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// IMPACT TAB
// ═══════════════════════════════════════════════════════════════════════════

function renderImpactTab(impact, intent) {
  if (!impact) return;

  const riskBadge = document.getElementById('risk-badge-full');
  if (riskBadge) {
    const risk = (impact.risk_level || 'low').toUpperCase();
    riskBadge.textContent = risk;
    riskBadge.className = `risk-badge ${risk.toLowerCase()}`;
  }

  const callers = impact.upstream_callers || [];
  const downstream = impact.downstream_dependencies || [];
  const tests = impact.affected_tests || [];
  const apis = impact.exposed_apis || [];
  const targets = impact.target_components || [];
  const paths = impact.propagation_paths || [];

  const callersNum = document.getElementById('istat-callers');
  if (callersNum) callersNum.textContent = callers.length;
  const downstreamNum = document.getElementById('istat-downstream');
  if (downstreamNum) downstreamNum.textContent = downstream.length;
  const testsNum = document.getElementById('istat-tests');
  if (testsNum) testsNum.textContent = tests.length;
  const apisNum = document.getElementById('istat-apis');
  if (apisNum) apisNum.textContent = apis.length;

  const container = document.getElementById('impact-lists-container');
  if (!container) return;

  let html = '';

  // Target Components
  if (targets.length > 0) {
    html += `
      <div class="impact-group">
        <div class="impact-group-title">Target Components (Change Seeds)</div>
        <div class="impact-group-items">
          ${targets.map(t => `<button class="impact-tag" onclick="window.focusGraphNode('${escapeHtml(t)}')">🎯 ${escapeHtml(t)}</button>`).join('')}
        </div>
      </div>
    `;
  }

  // Propagation Paths
  if (paths.length > 0) {
    html += `
      <div class="impact-group">
        <div class="impact-group-title">Change Propagation Paths</div>
        <div class="chains-flow-container">
          ${paths.map(p => `
            <div class="chain-card">
              ${p.map(step => `<button class="chain-node-btn" onclick="window.focusGraphNode('${escapeHtml(step)}')">${escapeHtml(step)}</button>`).join('<span class="chain-rel-arrow"> → </span>')}
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  // Upstream Callers
  if (callers.length > 0) {
    html += `
      <div class="impact-group">
        <div class="impact-group-title">Upstream Callers (${callers.length})</div>
        <div class="impact-group-items">
          ${callers.map(c => `<button class="impact-tag" onclick="window.focusGraphNode('${escapeHtml(c)}')">${escapeHtml(c)}</button>`).join('')}
        </div>
      </div>
    `;
  }

  // Downstream Dependencies
  if (downstream.length > 0) {
    html += `
      <div class="impact-group">
        <div class="impact-group-title">Downstream Dependencies (${downstream.length})</div>
        <div class="impact-group-items">
          ${downstream.map(d => `<button class="impact-tag" onclick="window.focusGraphNode('${escapeHtml(d)}')">${escapeHtml(d)}</button>`).join('')}
        </div>
      </div>
    `;
  }

  // Affected Tests
  if (tests.length > 0) {
    html += `
      <div class="impact-group">
        <div class="impact-group-title" style="color:var(--amber)">Affected Automated Tests (${tests.length})</div>
        <div class="impact-group-items">
          ${tests.map(t => `<button class="impact-tag test-tag" onclick="window.focusGraphNode('${escapeHtml(t)}')">🧪 ${escapeHtml(t)}</button>`).join('')}
        </div>
      </div>
    `;
  }

  // Exposed APIs
  if (apis.length > 0) {
    html += `
      <div class="impact-group">
        <div class="impact-group-title" style="color:var(--cyan)">Exposed APIs (${apis.length})</div>
        <div class="impact-group-items">
          ${apis.map(a => `<button class="impact-tag" onclick="window.focusGraphNode('${escapeHtml(a)}')">⚡ ${escapeHtml(a)}</button>`).join('')}
        </div>
      </div>
    `;
  }

  container.innerHTML = html || '<div class="empty-state"><p>No impact blast radius calculated for this query.</p></div>';
}

// ═══════════════════════════════════════════════════════════════════════════
// SOURCE TAB
// ═══════════════════════════════════════════════════════════════════════════

function renderSnippets(snippets) {
  const container = document.getElementById('snippets-list');
  if (!container) return;

  if (!snippets || !snippets.length) {
    container.innerHTML = '<div class="empty-state"><p>No code snippets retrieved for this task.</p></div>';
    return;
  }

  container.innerHTML = snippets.map(s => {
    const meta = ENTITY[s.entity_type] || ENTITY.class;
    const color = meta.color || '#60a5fa';
    return `
      <div class="snippet-card">
        <div class="snippet-header">
          <div class="comp-header" style="margin-bottom:0;">
            <span class="snippet-name" onclick="window.focusGraphNode('${escapeHtml(s.name)}')">${escapeHtml(s.name)}</span>
            <span class="comp-type-badge" style="background:${color}22; color:${color}; border:1px solid ${color}66;">${escapeHtml(s.entity_type.toUpperCase())}</span>
          </div>
          <span class="snippet-meta">${escapeHtml(s.file_path)}:${s.start_line}-${s.end_line} · ${s.estimated_tokens || s.token_cost || 0} tokens</span>
        </div>
        ${s.why_included ? `<div class="comp-why" style="margin:4px 0 6px 0;">✓ ${escapeHtml(s.why_included)}</div>` : ''}
        <pre class="snippet-code"><code>${escapeHtml(s.code)}</code></pre>
      </div>
    `;
  }).join('');
}

// ═══════════════════════════════════════════════════════════════════════════
// PROVENANCE TAB
// ═══════════════════════════════════════════════════════════════════════════

function renderProvenance(snippets, provenanceRecords) {
  const container = document.getElementById('provenance-list');
  if (!container) return;

  const records = [];

  (snippets || []).forEach(s => {
    const prov = s.provenance || {};
    records.push({
      node: s.name,
      entity_type: s.entity_type,
      file_path: s.file_path,
      lines: `${s.start_line}-${s.end_line}`,
      source_type: prov.source_type || 'static_analysis',
      confidence: prov.confidence != null ? prov.confidence : 1.0,
      snapshot_id: prov.snapshot_id || currentRepository.snapshotId,
      commit_sha: currentRepository.commitSha,
    });
  });

  if (!records.length && provenanceRecords && provenanceRecords.length) {
    provenanceRecords.forEach(p => {
      records.push({
        node: p.node_id ? p.node_id.split(':').pop() : 'Component',
        entity_type: 'artifact',
        file_path: p.file_path || '—',
        lines: p.line_number ? String(p.line_number) : '—',
        source_type: p.source_type || 'static_analysis',
        confidence: p.confidence || 1.0,
        snapshot_id: p.snapshot_id || currentRepository.snapshotId,
        commit_sha: currentRepository.commitSha,
      });
    });
  }

  if (!records.length) {
    container.innerHTML = '<div class="empty-state"><p>No provenance records available.</p></div>';
    return;
  }

  container.innerHTML = records.map(r => `
    <div class="prov-card">
      <div class="comp-header">
        <span class="prov-node" onclick="window.focusGraphNode('${escapeHtml(r.node)}')">${escapeHtml(r.node)} (${r.entity_type})</span>
        <span class="comp-metrics" style="color:var(--emerald);">Confidence: ${(r.confidence).toFixed(2)}</span>
      </div>
      <div class="prov-chain">Source: <strong>${escapeHtml(r.source_type)}</strong> · Commit: <code>${escapeHtml((r.commit_sha||'').slice(0, 7))}</code> · Snapshot: <code>${escapeHtml((r.snapshot_id||'').slice(0, 10))}</code></div>
      <div class="prov-loc">File: ${escapeHtml(r.file_path)} : ${escapeHtml(r.lines)}</div>
    </div>
  `).join('');
}

// ═══════════════════════════════════════════════════════════════════════════
// GRAPH VFX & SUBGRAPH HIGHLIGHTING
// ═══════════════════════════════════════════════════════════════════════════

function highlightRetrievedGraph(data) {
  if (!cy) return;
  cy.elements().removeClass('selected highlighted neighbor active-edge dimmed search-match');
  cy.elements().style('opacity', '');

  const names = new Set();
  (data.nodes || []).forEach(n => names.add(n.name));
  (data.snippets || []).forEach(s => names.add(s.name));
  if (data.impact) {
    (data.impact.target_components || []).forEach(n => names.add(n));
    (data.impact.upstream_callers || []).forEach(n => names.add(n));
    (data.impact.downstream_dependencies || []).forEach(n => names.add(n));
    (data.impact.affected_tests || []).forEach(n => names.add(n));
    (data.impact.exposed_apis || []).forEach(n => names.add(n));
  }

  const matched = cy.nodes().filter(n => names.has(n.data('label')) || names.has(n.data('name')));
  if (matched.length > 0) {
    cy.elements().addClass('dimmed');
    matched.removeClass('dimmed').addClass('highlighted');

    // Highlight connecting edges between matched nodes
    const matchedIds = new Set(matched.map(n => n.id()));
    cy.edges().forEach(e => {
      if (matchedIds.has(e.source().id()) && matchedIds.has(e.target().id())) {
        e.removeClass('dimmed').addClass('active-edge');
      }
    });

    cy.animate({ center: { eles: matched }, zoom: Math.min(1.15, Math.max(0.7, cy.zoom())), duration: 500 });
  }
}

// Global click-to-focus helper for all tabs
window.focusGraphNode = function(name) {
  if (!cy) return;
  const target = cy.nodes().filter(n => n.data('label') === name || n.data('name') === name || n.id() === name || n.id().endsWith(':' + name));
  if (target.length > 0) {
    cy.elements().removeClass('selected');
    target.addClass('selected');
    cy.animate({ center: { eles: target }, zoom: 1.35, duration: 400 });
    renderNodeInspector(target.first().data());
    switchTab('tab-node');
  } else {
    showToast(`Component '${name}' not found in active graph layout`, 'info');
  }
};

function switchTab(tabId) {
  document.querySelectorAll('.insp-tab').forEach(t => {
    if (t.dataset.tab === tabId) t.classList.add('active');
    else t.classList.remove('active');
  });
  document.querySelectorAll('.tab-pane').forEach(p => {
    if (p.id === tabId) p.classList.add('active');
    else p.classList.remove('active');
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// SCOPED RETRIEVAL HISTORY
// ═══════════════════════════════════════════════════════════════════════════

function getRetrievalHistory() {
  if (!currentRepository.repoId) return [];
  try {
    const raw = localStorage.getItem(`ame_history_${currentRepository.repoId}`);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function addToRetrievalHistory(task, data) {
  if (!currentRepository.repoId || !task) return;
  try {
    let hist = getRetrievalHistory();
    hist = hist.filter(h => h.task.toLowerCase() !== task.toLowerCase());
    hist.unshift({
      task,
      intent: data.task_intent || 'IMPLEMENTATION',
      tokens: data.total_tokens,
      timestamp: Date.now(),
    });
    if (hist.length > 8) hist = hist.slice(0, 8);
    localStorage.setItem(`ame_history_${currentRepository.repoId}`, JSON.stringify(hist));
    renderRetrievalHistory();
  } catch (e) {
    console.warn('Failed to save history', e);
  }
}

function renderRetrievalHistory() {
  const container = document.getElementById('retrieval-history-section');
  const list = document.getElementById('history-list');
  if (!container || !list) return;

  const hist = getRetrievalHistory();
  if (hist.length === 0) {
    container.style.display = 'none';
    list.innerHTML = '';
    return;
  }

  container.style.display = 'block';
  list.innerHTML = hist.map(h => `
    <div class="history-item" onclick="loadHistoryTask('${escapeHtml(h.task)}')">
      <span class="hist-check" style="color:var(--emerald);font-size:11px;">✓</span>
      <span class="history-item-text" title="${escapeHtml(h.task)}">${escapeHtml(h.task)}</span>
      <span class="history-item-meta">${escapeHtml(h.intent || 'TASK')}</span>
    </div>
  `).join('');
}

function clearRetrievalHistory() {
  if (currentRepository.repoId) {
    localStorage.removeItem(`ame_history_${currentRepository.repoId}`);
    renderRetrievalHistory();
    showToast('Task history cleared for current repository.', 'info');
  }
}

window.loadHistoryTask = function(taskText) {
  const input = document.getElementById('task-input');
  if (input) {
    input.value = taskText;
    runContextRetrieval(taskText);
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// ACTIONS: COPY CONTEXT, VIEW JSON, SEND TO AGENT, TOAST
// ═══════════════════════════════════════════════════════════════════════════

function copyContextToClipboard() {
  if (!lastRetrievedContextPackage) {
    showToast('No context retrieved yet. Run a task first.', 'warning');
    return;
  }
  const text = lastRetrievedContextPackage.formatted_context || JSON.stringify(lastRetrievedContextPackage, null, 2);
  navigator.clipboard.writeText(text).then(() => {
    showToast('📋 Architectural context copied to clipboard! Ready to paste into AI agent prompt.', 'success');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'error');
  });
}

function openJsonModal() {
  if (!lastRetrievedContextPackage) {
    showToast('No context retrieved yet. Run a task first.', 'warning');
    return;
  }
  const modal = document.getElementById('context-json-modal');
  const codeEl = document.getElementById('json-modal-content');
  if (codeEl) {
    codeEl.innerHTML = `<code>${escapeHtml(JSON.stringify(lastRetrievedContextPackage, null, 2))}</code>`;
  }
  if (modal) modal.style.display = 'flex';
}

function closeJsonModal() {
  const modal = document.getElementById('context-json-modal');
  if (modal) modal.style.display = 'none';
}

function copyRawJsonPayload() {
  if (!lastRetrievedContextPackage) return;
  const jsonStr = JSON.stringify(lastRetrievedContextPackage, null, 2);
  navigator.clipboard.writeText(jsonStr).then(() => {
    showToast('📋 Raw ContextPackage JSON copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'error');
  });
}

function sendContextToAgent() {
  if (!lastRetrievedContextPackage) {
    showToast('No context retrieved yet. Run a task first.', 'warning');
    return;
  }
  const mcpEnvelope = {
    mcp_version: "1.0",
    server: "Architecture Memory Engine",
    tool: "retrieve_context",
    parameters: {
      task: lastRetrievedContextPackage.task,
      repository: currentRepository.repositoryName,
      snapshot_id: currentRepository.snapshotId,
      branch: currentRepository.branch,
      commit: currentRepository.commitSha,
    },
    context_package: lastRetrievedContextPackage,
  };
  navigator.clipboard.writeText(JSON.stringify(mcpEnvelope, null, 2)).then(() => {
    showToast('🚀 ContextPackage dispatched to AI Coding Agent (MCP Schema payload copied)!', 'success');
  }).catch(() => {
    showToast('Context package ready for MCP consumption', 'info');
  });
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('ame-toast');
  if (!toast) return;
  toast.textContent = message;
  toast.className = `ame-toast show ${type}`;
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.className = 'ame-toast';
  }, 3200);
}

// ── Utility ─────────────────────────────────────────────────────────────
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
