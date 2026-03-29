import { useEffect, useRef, useState } from 'react'

type InputField = {
  key: string
  label: string
  kind: 'number' | 'boolean' | 'text'
  description: string
  placeholder?: string | null
}

type Guide = {
  what_it_does: string
  what_you_need: string[]
  what_result_means: string[]
  next_steps: string[]
}

type ModelDefinition = {
  slug: string
  title: string
  owner: string
  hub_url: string
  model_cid: string
  category: string
  summary: string
  input_key: string
  input_shape: string
  result_keys: string[]
  input_fields: InputField[]
  sample_input: Record<string, number | string | boolean>
  guide: Guide
}

type ResolveResponse = {
  model: ModelDefinition
}

type ModelListResponse = {
  models: ModelDefinition[]
}

type LeaderboardEntry = {
  rank: number
  source: 'curated' | 'user'
  model_slug: string | null
  model_title: string | null
  model_category: string | null
  name: string
  protocol_url: string
  summary: string
  created_at: string | null
  headline_score: string | null
  headline_label: string | null
  normalized_input: Record<string, unknown>
  result: Record<string, unknown>
}

type BridgeLeaderboardResponse = {
  model: ModelDefinition
  entries: LeaderboardEntry[]
}

type ModelUsageStat = {
  model_slug: string
  model_title: string
  runs: number
}

type GlobalLeaderboardResponse = {
  entries: LeaderboardEntry[]
  model_usage: ModelUsageStat[]
}

type RunResponse = {
  model: ModelDefinition
  normalized_input: Record<string, unknown>
  result: Record<string, unknown>
  ai_explanation: string
  execution_mode: 'live' | 'demo'
  transaction_hash: string | null
  warnings: string[]
  comparison: RunResponse[]
}

type BridgeSortKey = 'risk_score' | 'tvl_usd' | 'prior_incidents'
type ViewTab = 'runner' | 'protocol' | 'leaderboard'

const defaultModelRef = 'https://hub.opengradient.ai/models/Goldy/Governance-Capture-Risk-Scorer'
const defaultTargetUrl = ''
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`
}

function App() {
  const [modelRef, setModelRef] = useState(defaultModelRef)
  const [targetUrl, setTargetUrl] = useState(defaultTargetUrl)
  const [models, setModels] = useState<ModelDefinition[]>([])
  const [model, setModel] = useState<ModelDefinition | null>(null)
  const [runResult, setRunResult] = useState<RunResponse | null>(null)
  const [bridgeLeaderboard, setBridgeLeaderboard] = useState<LeaderboardEntry[]>([])
  const [globalLeaderboard, setGlobalLeaderboard] = useState<LeaderboardEntry[]>([])
  const [modelUsage, setModelUsage] = useState<ModelUsageStat[]>([])
  const [bridgeSort, setBridgeSort] = useState<BridgeSortKey>('risk_score')
  const [activeTab, setActiveTab] = useState<ViewTab>('runner')
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showGuideDetails, setShowGuideDetails] = useState(false)
  const [leaderboardFresh, setLeaderboardFresh] = useState(false)
  const [loadingModel, setLoadingModel] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const modelMenuRef = useRef<HTMLDivElement | null>(null)

  const selectedModelOption = models.some((item) => item.hub_url === modelRef) ? modelRef : '__custom__'
  const hasProtocolUrl = Boolean(normalizePreviewUrl(targetUrl))

  useEffect(() => {
    void loadModels()
    void resolveModel(defaultModelRef)
    void loadGlobalLeaderboard()
  }, [])

  useEffect(() => {
    if (model?.slug === 'cross-chain-bridge-risk-classifier') {
      void loadBridgeLeaderboard()
      return
    }

    setBridgeLeaderboard([])
  }, [model])

  useEffect(() => {
    if (!hasProtocolUrl && activeTab === 'protocol') {
      setActiveTab('runner')
    }
  }, [activeTab, hasProtocolUrl])

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!modelMenuRef.current) {
        return
      }

      if (!modelMenuRef.current.contains(event.target as Node)) {
        setShowModelMenu(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setShowModelMenu(false)
      }
    }

    window.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('keydown', handleEscape)
    return () => {
      window.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('keydown', handleEscape)
    }
  }, [])

  async function loadModels() {
    try {
      const response = await fetch(apiUrl('/api/models'))
      if (!response.ok) {
        throw new Error('Model gallery failed to load.')
      }

      const payload = (await response.json()) as ModelListResponse
      setModels(payload.models)
    } catch {
      setModels([])
    }
  }

  async function resolveModel(ref: string) {
    setLoadingModel(true)
    setError(null)
    setRunResult(null)

    try {
      const response = await fetch(apiUrl('/api/models/resolve'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_ref: ref }),
      })

      if (!response.ok) {
        throw new Error('Model was not resolved. Check the OpenGradient URL, slug, or CID.')
      }

      const payload = (await response.json()) as ResolveResponse
      setModel(payload.model)
    } catch (err) {
      setModel(null)
      setError(err instanceof Error ? err.message : 'Unknown resolve error.')
    } finally {
      setLoadingModel(false)
    }
  }

  async function loadBridgeLeaderboard() {
    try {
      const response = await fetch(apiUrl('/api/leaderboards/bridges'))
      if (!response.ok) {
        throw new Error('Bridge leaderboard failed to load.')
      }

      const payload = (await response.json()) as BridgeLeaderboardResponse
      setBridgeLeaderboard(payload.entries)
    } catch {
      setBridgeLeaderboard([])
    }
  }

  async function loadGlobalLeaderboard() {
    try {
      const response = await fetch(apiUrl('/api/leaderboards/global'))
      if (!response.ok) {
        throw new Error('Global leaderboard failed to load.')
      }

      const payload = (await response.json()) as GlobalLeaderboardResponse
      setGlobalLeaderboard(payload.entries)
      setModelUsage(payload.model_usage)
    } catch {
      setGlobalLeaderboard([])
      setModelUsage([])
    }
  }

  async function runModel() {
    if (!model) {
      return
    }

    if (!targetUrl.trim()) {
      setError('Protocol URL is required.')
      return
    }

    setRunning(true)
    setError(null)

    try {
      const response = await fetch(apiUrl('/api/models/run'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_ref: modelRef,
          mode: 'url',
          target_url: normalizePreviewUrl(targetUrl),
        }),
      })

      if (!response.ok) {
        throw new Error('Model execution failed.')
      }

      const payload = (await response.json()) as RunResponse
      setRunResult(payload)
      await loadGlobalLeaderboard()
      setLeaderboardFresh(true)

      if (model.slug === 'cross-chain-bridge-risk-classifier') {
        await loadBridgeLeaderboard()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown run error.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="og-room">
      <div className="lamp-glow" />
      <div className="room-noise" />

      <main className="stage-shell">
        <section className="computer-body">
          <div className="monitor-frame">
            <div className="monitor-screen">
              <div className="screen-overlay" />

              <div className="screen-content">
                <div className="screen-header">
                  <span className="screen-badge">OG Runner</span>
                  <span className="screen-meta">{model?.category ?? 'Model not loaded'}</span>
                </div>

                <div className="view-tabs">
                  {([
                    ['runner', 'Runner'],
                    ...(hasProtocolUrl ? ([['protocol', 'Protocol']] as const) : []),
                    ['leaderboard', 'Leaderboard'],
                  ] as const).map(([value, label]) => (
                    <button
                      key={value}
                      className={`view-tab ${activeTab === value ? 'view-tab-active' : ''}`}
                      onClick={() => {
                        setActiveTab(value)
                        if (value === 'leaderboard') {
                          setLeaderboardFresh(false)
                        }
                      }}
                      type="button"
                    >
                      {label}
                      {value === 'leaderboard' && leaderboardFresh ? <span className="tab-indicator">New</span> : null}
                    </button>
                  ))}
                </div>

                {activeTab === 'runner' ? (
                  <div className="screen-layout">
                    <div className="screen-form">
                      <label className="field-shell">
                        <span className="field-label">Model</span>
                        <div className="picker-shell" ref={modelMenuRef}>
                          <button
                            className={`screen-input picker-trigger ${showModelMenu ? 'picker-trigger-open' : ''}`}
                            onClick={() => setShowModelMenu((value) => !value)}
                            type="button"
                          >
                            <span>{selectedModelOption === '__custom__' ? 'Custom model ref' : shortTitle(model?.title ?? 'Select a model')}</span>
                            <span className="picker-caret">{showModelMenu ? '−' : '+'}</span>
                          </button>

                          {showModelMenu ? (
                            <div className="picker-menu">
                              {models.map((item) => (
                                <button
                                  key={item.slug}
                                  className={`picker-option ${model?.slug === item.slug ? 'picker-option-active' : ''}`}
                                  onClick={() => {
                                    setModelRef(item.hub_url)
                                    setShowModelMenu(false)
                                    void resolveModel(item.hub_url)
                                  }}
                                  type="button"
                                >
                                  <span className="picker-option-title">{shortTitle(item.title)}</span>
                                  <span className="picker-option-meta">{item.summary}</span>
                                </button>
                              ))}

                              <button
                                className={`picker-option ${selectedModelOption === '__custom__' ? 'picker-option-active' : ''}`}
                                onClick={() => {
                                  setShowAdvanced(true)
                                  setModelRef('')
                                  setShowModelMenu(false)
                                }}
                                type="button"
                              >
                                <span className="picker-option-title">Custom model ref</span>
                                <span className="picker-option-meta">Paste your own model URL, slug, or CID</span>
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </label>

                      <div className="inline-note inline-note-compact">
                        <span className="inline-note-key">Model purpose</span>
                        <span>
                          {model?.summary ??
                            'Choose a specific model first. The selected model decides how the site, bridge, DEX, or protocol page will be scored.'}
                        </span>
                        {model ? (
                          <div className="context-chip-row">
                            <span className="context-chip">Target: {getModelTargetLabel(model)}</span>
                            <span className="context-chip">Output: {getModelOutputLabel(model)}</span>
                          </div>
                        ) : null}
                      </div>

                      <div className="action-row action-row-compact">
                        <button
                          className={`screen-button screen-button-muted ${showAdvanced ? 'screen-button-active' : ''}`}
                          onClick={() => setShowAdvanced((value) => !value)}
                          type="button"
                        >
                          {showAdvanced ? 'Hide advanced' : 'Advanced'}
                        </button>
                      </div>

                      {showAdvanced ? (
                        <>
                          <label className="field-shell">
                            <span className="field-label">Your model ref</span>
                            <input
                              className="screen-input"
                              value={modelRef}
                              onChange={(event) => setModelRef(event.target.value)}
                              placeholder="Enter your model"
                            />
                          </label>

                          <div className="inline-note inline-note-compact">
                            <span className="inline-note-key">Advanced</span>
                            <span>Paste your own model URL, slug, or CID here. This field is only for a custom model reference.</span>
                          </div>

                          <div className="action-row action-row-compact">
                            <button
                              className="screen-button screen-button-muted"
                              onClick={() => void resolveModel(modelRef)}
                              disabled={loadingModel}
                              type="button"
                            >
                              {loadingModel ? 'Loading model...' : 'Load model'}
                            </button>
                          </div>
                        </>
                      ) : null}

                      <label className="field-shell">
                        <span className="field-label">Protocol URL</span>
                        <input
                          className="screen-input"
                          value={targetUrl}
                          onChange={(event) => setTargetUrl(event.target.value)}
                          placeholder={getTargetHint(model)}
                        />
                      </label>

                      <div className="inline-note inline-note-compact">
                        <span className="inline-note-key">How it works</span>
                        <span>
                          Pick a specific model, then paste the site, bridge, DEX, stablecoin, or protocol page you want that model to analyze.
                        </span>
                      </div>

                      <div className="inline-note">
                        <div className="inline-note-head">
                          <span className="inline-note-key">Model guide</span>
                          <button
                            className="inline-note-toggle"
                            onClick={() => setShowGuideDetails((value) => !value)}
                            type="button"
                          >
                            {showGuideDetails ? 'Less' : 'More'}
                          </button>
                        </div>
                        <span>{model?.guide.what_it_does ?? 'Load a model to start scanning a protocol or bridge page.'}</span>
                        {showGuideDetails && model ? (
                          <div className="inline-note-details">
                            <p>{model.summary}</p>
                            <p>Input: {model.input_shape}</p>
                            <p>Outputs: {model.result_keys.slice(0, 4).join(', ') || 'Model-specific result fields'}</p>
                          </div>
                        ) : null}
                      </div>

                      <div className="action-row">
                        <button className="screen-button" onClick={() => void runModel()} disabled={!model || running} type="button">
                          {running ? getRunningLabel(model) : getRunLabel(model)}
                        </button>
                      </div>

                      {error ? <p className="status-line status-line-error">{error}</p> : null}
                    </div>

                    <RunnerPreviewPanel model={model} runResult={runResult} targetUrl={targetUrl} />
                  </div>
                ) : null}

                {activeTab === 'protocol' && hasProtocolUrl ? <ProtocolViewport url={targetUrl} /> : null}

                {activeTab === 'leaderboard' ? (
                  <LeaderboardTab
                    entries={globalLeaderboard}
                    modelUsage={modelUsage}
                    bridgeEntries={bridgeLeaderboard}
                    currentRun={runResult}
                    sortKey={bridgeSort}
                    onSortChange={setBridgeSort}
                    showBridgeBoard={model?.slug === 'cross-chain-bridge-risk-classifier' && bridgeLeaderboard.length > 0}
                  />
                ) : null}
              </div>
            </div>
          </div>

          <div className="computer-stand" />
          <div className="computer-base" />
        </section>
      </main>
    </div>
  )
}

function SiteBackdrop({ url }: { url: string }) {
  const normalizedUrl = normalizePreviewUrl(url)
  const host = getHostLabel(normalizedUrl)

  if (!normalizedUrl) {
    return null
  }

  return (
    <div className="site-backdrop">
      <div className="site-backdrop-frame">
        <iframe
          title="site-preview"
          src={normalizedUrl}
          className="site-backdrop-iframe"
          loading="lazy"
          referrerPolicy="no-referrer"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>
      <div className="site-backdrop-fade" />
      <div className="site-backdrop-label">{host}</div>
    </div>
  )
}

function StatCard({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="stat-card">
      <p className="panel-kicker">{label}</p>
      <p className="stat-value">{value}</p>
    </div>
  )
}

function BridgeLeaderboardPanel({
  entries,
  currentRun,
  sortKey,
  onSortChange,
}: {
  entries: LeaderboardEntry[]
  currentRun: RunResponse | null
  sortKey: BridgeSortKey
  onSortChange: (value: BridgeSortKey) => void
}) {
  const sortedEntries = sortBridgeEntries(entries, sortKey)
  const currentRiskScore = Number(currentRun?.result.risk_score ?? Number.NaN)
  const riskSortedEntries = sortBridgeEntries(entries, 'risk_score')
  const rankedCurrentPosition =
    Number.isFinite(currentRiskScore)
      ? riskSortedEntries.filter((entry) => Number(entry.result.risk_score ?? 0) < currentRiskScore).length + 1
      : null

  return (
    <div>
      <div className="leaderboard-headline">
        <div>
          <p className="panel-kicker">Bridge leaderboard</p>
          <h3>Common bridge set plus saved user runs.</h3>
        </div>
        {rankedCurrentPosition ? <span className="leaderboard-rank">Latest run would place #{rankedCurrentPosition}</span> : null}
      </div>

      <div className="chip-row">
        {([
          ['risk_score', 'Risk'],
          ['tvl_usd', 'TVL'],
          ['prior_incidents', 'Incidents'],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            className={`choice-chip ${sortKey === value ? 'choice-chip-active' : ''}`}
            onClick={() => onSortChange(value)}
            type="button"
          >
            Sort: {label}
          </button>
        ))}
      </div>

      <div className="leaderboard-list">
        {sortedEntries.slice(0, 8).map((entry, index) => (
          <a
            key={`${entry.source}-${entry.name}-${entry.created_at ?? index}`}
            className="leaderboard-item"
            href={entry.protocol_url}
            target="_blank"
            rel="noreferrer"
          >
            <span className="leaderboard-order">#{index + 1}</span>
            <div className="leaderboard-copy">
              <strong>{entry.name}</strong>
              <small>
                {entry.source === 'user' ? 'User run' : 'Curated profile'} · {entry.summary}
                {entry.created_at ? ` · ${formatRelativeTime(entry.created_at)}` : ''}
              </small>
            </div>
            <span className="leaderboard-score">{String(entry.result.risk_score ?? '-')}</span>
            <span className="leaderboard-category">{String(entry.result.risk_category ?? '-')}</span>
          </a>
        ))}
      </div>
    </div>
  )
}

function GlobalLeaderboardPanel({
  entries,
  modelUsage,
}: {
  entries: LeaderboardEntry[]
  modelUsage: ModelUsageStat[]
}) {
  const activeModelCount = new Set(entries.map((entry) => entry.model_slug).filter(Boolean)).size
  const activeSiteCount = new Set(entries.map((entry) => entry.protocol_url)).size

  return (
    <div className="activity-shell">
      <div className="activity-column">
        <div className="activity-head">
          <div>
            <p className="panel-kicker">Live board</p>
            <p className="activity-subtitle">What people just ran across OG models.</p>
          </div>
          <span className="activity-count">
            {entries.length} runs / {activeModelCount || 0} models
          </span>
        </div>
        <div className="activity-list">
          {entries.slice(0, 4).map((entry, index) => (
            <a
              key={`${entry.created_at ?? 'saved'}-${entry.name}-${entry.protocol_url}-${index}`}
              className="activity-item"
              href={entry.protocol_url}
              target="_blank"
              rel="noreferrer"
            >
              <span className="activity-order">#{index + 1}</span>
              <div className="activity-copy">
                <strong>{entry.name}</strong>
                <small>{entry.model_title ?? 'Saved run'}</small>
                <div className="activity-tags">
                  <span className="activity-tag">{entry.model_category ?? 'Unknown model'}</span>
                  <span className="activity-tag">{entry.headline_score ?? '-'}</span>
                  <span className="activity-tag">{entry.headline_label ?? '-'}</span>
                  <span className="activity-tag">{entry.source === 'user' ? 'User run' : 'Curated'}</span>
                </div>
              </div>
              <span className="activity-time">{entry.created_at ? formatRelativeTime(entry.created_at) : 'saved'}</span>
            </a>
          ))}
          {entries.length === 0 ? <p className="activity-empty">No saved runs yet.</p> : null}
        </div>
      </div>

      <div className="activity-column">
        <div className="activity-head">
          <div>
            <p className="panel-kicker">Most used models</p>
            <p className="activity-subtitle">Traffic across protocols and experiments.</p>
          </div>
          <span className="activity-count">{activeSiteCount} sites</span>
        </div>
        <div className="usage-pills">
          {modelUsage.slice(0, 5).map((item) => (
            <div key={item.model_slug} className="usage-pill">
              <strong>{shortTitle(item.model_title)}</strong>
              <span>{item.runs} runs</span>
              <div className="usage-meter">
                <span
                  className="usage-meter-fill"
                  style={{
                    width: `${Math.max(18, Math.min(100, (item.runs / Math.max(modelUsage[0]?.runs ?? 1, 1)) * 100))}%`,
                  }}
                />
              </div>
            </div>
          ))}
          {modelUsage.length === 0 ? <p className="activity-empty">Usage stats will appear after people run models.</p> : null}
        </div>
      </div>
    </div>
  )
}

function RunnerPreviewPanel({
  model,
  runResult,
  targetUrl,
}: {
  model: ModelDefinition | null
  runResult: RunResponse | null
  targetUrl: string
}) {
  return (
    <div className="screen-output screen-preview-panel">
      <SiteBackdrop url={targetUrl} />
      <div className="preview-shade" />

      <div className="preview-content">
        {runResult && model ? (
          <>
            <div className="result-hero">
              <div className="result-headline result-headline-compact">
                <div>
                  <p className="result-kicker">Score</p>
                  <p className="result-score">{getHeadlineScore(model, runResult.result)}</p>
                  <p className="result-meta">{getScoreMeta(model, runResult.result)}</p>
                </div>

                <div className="result-meta-panels">
                  <StatCard label="Mode" value={runResult.execution_mode} />
                  <StatCard label="Site" value={getHostLabel(normalizePreviewUrl(targetUrl))} />
                </div>
              </div>

              <div className="result-summary-strip">
                <div className="result-summary-chip">
                  <span className="panel-kicker">Model</span>
                  <strong>{shortTitle(model.title)}</strong>
                </div>
                <div className="result-summary-chip">
                  <span className="panel-kicker">Verdict</span>
                  <strong>{getScoreMeta(model, runResult.result)}</strong>
                </div>
                <div className="result-summary-chip">
                  <span className="panel-kicker">Source</span>
                  <strong>{getHostLabel(normalizePreviewUrl(targetUrl))}</strong>
                </div>
              </div>
            </div>

            <div className="result-grid result-grid-stack">
              <div className="result-card">
                <p className="panel-kicker">Quick read</p>
                <p className="result-explanation">{runResult.ai_explanation}</p>
                <div className="parameter-scale-list">
                  <p className="panel-kicker">Model parameters</p>
                  <ParameterScaleList model={model} result={runResult.result} />
                </div>
                <div className="detail-grid">
                  {getScoreDetails(model, runResult.result).map(([key, value]) => (
                    <StatCard key={key} label={key} value={value} />
                  ))}
                </div>
              </div>
            </div>

            {runResult.warnings.length > 0 ? <div className="status-line">{runResult.warnings.join(' ')}</div> : null}
          </>
        ) : (
          <div className="empty-state preview-empty-state">
            <p className="panel-kicker">Protocol viewport</p>
            <p>
              {model
                ? `The ${getModelTargetLabel(model)} will load here, followed by the ${getModelOutputLabel(model).toLowerCase()}, parameter scales, and summary.`
                : 'The protocol site will load here, followed by the model result, parameter scales, and summary.'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function ProtocolViewport({ url }: { url: string }) {
  return (
    <div className="screen-output screen-preview-panel protocol-panel">
      <SiteBackdrop url={url} />
      <div className="preview-shade" />
      <div className="preview-content protocol-panel-copy">
        <div className="protocol-panel-note">
          <p className="panel-kicker">Protocol</p>
          <p>This panel shows the live protocol page the model is analyzing in the background.</p>
        </div>
      </div>
    </div>
  )
}

function LeaderboardTab({
  entries,
  modelUsage,
  bridgeEntries,
  currentRun,
  sortKey,
  onSortChange,
  showBridgeBoard,
}: {
  entries: LeaderboardEntry[]
  modelUsage: ModelUsageStat[]
  bridgeEntries: LeaderboardEntry[]
  currentRun: RunResponse | null
  sortKey: BridgeSortKey
  onSortChange: (value: BridgeSortKey) => void
  showBridgeBoard: boolean
}) {
  return (
    <div className="leaderboard-tab">
      <div className="leaderboard-tab-panel">
        <GlobalLeaderboardPanel entries={entries} modelUsage={modelUsage} />
      </div>

      {showBridgeBoard ? (
        <div className="leaderboard-tab-panel">
          <BridgeLeaderboardPanel
            entries={bridgeEntries}
            currentRun={currentRun}
            sortKey={sortKey}
            onSortChange={onSortChange}
          />
        </div>
      ) : null}
    </div>
  )
}

function ParameterScaleList({
  model,
  result,
}: {
  model: ModelDefinition
  result: Record<string, unknown>
}) {
  const entries: [string, number, string][] = getParameterScaleEntries(model, result)

  return (
    <div className="metric-list">
      {entries.map(([label, value, display]) => (
        <div key={label} className="metric-row">
          <div className="metric-copy">
            <span>{label}</span>
            <span>{display}</span>
          </div>
          <div className="metric-track">
            <div className="metric-fill" style={{ width: `${Math.max(6, value)}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function getHeadlineScore(model: ModelDefinition, result: Record<string, unknown>) {
  switch (model.slug) {
    case 'governance-capture-risk-scorer':
      return String(result.governance_capture_risk_score ?? '-')
    case 'cross-chain-bridge-risk-classifier':
      return String(result.risk_score ?? '-')
    case 'defi-protocol-health-score':
      return String(result.health_score ?? '-')
    case 'dex-liquidity-exit-risk-scorer':
      return String(result.liquidity_exit_risk_score ?? '-')
    case 'stablecoin-depeg-risk-monitor':
      return String(result.depeg_risk_score ?? '-')
    case 'nft-wash-trading-detector':
      return `${Math.round(Number(result.wash_probability ?? 0) * 100)}%`
    default:
      return '-'
  }
}

function getScoreMeta(model: ModelDefinition, result: Record<string, unknown>) {
  switch (model.slug) {
    case 'governance-capture-risk-scorer':
      return `Grade ${String(result.grade ?? '-')}`
    case 'cross-chain-bridge-risk-classifier':
      return String(result.risk_category ?? '-')
    case 'defi-protocol-health-score':
      return `Grade ${String(result.grade ?? '-')}`
    case 'dex-liquidity-exit-risk-scorer':
      return String(result.risk_level ?? '-')
    case 'stablecoin-depeg-risk-monitor':
      return String(result.alert ?? '-')
    case 'nft-wash-trading-detector':
      return String(result.verdict ?? '-')
    default:
      return model.title
  }
}

function getScoreDetails(model: ModelDefinition, result: Record<string, unknown>) {
  if (model.slug === 'governance-capture-risk-scorer') {
    return [
      ['Pressure', String(result.governance_capture_pressure ?? '-')],
      ['Flags', Array.isArray(result.flags) ? result.flags.join(', ') || 'None' : 'None'],
    ]
  }

  if (model.slug === 'cross-chain-bridge-risk-classifier') {
    return Object.entries((result.breakdown as Record<string, number> | undefined) ?? {})
      .slice(0, 4)
      .map(([key, value]) => [key, `${Math.round((value ?? 0) * 100)}%`])
  }

  if (model.slug === 'defi-protocol-health-score') {
    return Object.entries((result.pillar_scores as Record<string, number> | undefined) ?? {})
      .slice(0, 4)
      .map(([key, value]) => [key, `${Math.round(value ?? 0)}%`])
  }

  if (model.slug === 'dex-liquidity-exit-risk-scorer') {
    return [
      ['Grade', String(result.grade ?? '-')],
      ['Flags', Array.isArray(result.flags) ? result.flags.join(', ') || 'None' : 'None'],
    ]
  }

  if (model.slug === 'stablecoin-depeg-risk-monitor') {
    return Object.entries((result.pillar_scores as Record<string, number> | undefined) ?? {})
      .slice(0, 4)
      .map(([key, value]) => [key, `${Math.round(value ?? 0)}%`])
  }

  if (model.slug === 'nft-wash-trading-detector') {
    return [['Signal', 'Wallet overlap and trade cadence']]
  }

  return []
}

function getParameterScaleEntries(model: ModelDefinition, result: Record<string, unknown>): [string, number, string][] {
  if (model.slug === 'governance-capture-risk-scorer') {
    const flags = Array.isArray(result.flags) ? result.flags.length : 0
    return [
      ['risk score', clampPercent(Number(result.governance_capture_risk_score ?? 0)), String(result.governance_capture_risk_score ?? '0')],
      ['pressure', clampPercent(Number(result.governance_capture_pressure ?? 0)), String(result.governance_capture_pressure ?? '0')],
      ['flags', Math.min(flags * 18, 100), `${flags}`],
    ] as [string, number, string][]
  }

  if (model.slug === 'cross-chain-bridge-risk-classifier') {
    return toDisplayPercentEntries((result.breakdown as Record<string, number> | undefined) ?? {})
  }

  if (model.slug === 'defi-protocol-health-score') {
    return toDisplayPercentEntries((result.pillar_scores as Record<string, number> | undefined) ?? {})
  }

  if (model.slug === 'dex-liquidity-exit-risk-scorer') {
    return toDisplayPercentEntries((result.pillar_scores as Record<string, number> | undefined) ?? {})
  }

  if (model.slug === 'stablecoin-depeg-risk-monitor') {
    return toDisplayPercentEntries((result.pillar_scores as Record<string, number> | undefined) ?? {})
  }

  if (model.slug === 'nft-wash-trading-detector') {
    const value = clampPercent(Number(result.wash_probability ?? 0) * 100)
    return [['wash probability', value, `${value}%`]]
  }

  return [] as [string, number, string][]
}

function toDisplayPercentEntries(record: Record<string, number>) {
  return Object.entries(record)
    .slice(0, 6)
    .map(([key, value]) => {
      const percent = clampPercent(value <= 1 ? value * 100 : value)
      return [key, percent, `${percent}%`] as [string, number, string]
    })
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function getTargetHint(model: ModelDefinition | null) {
  if (!model) {
    return 'Paste the site you want the model to inspect.'
  }

  if (model.slug.includes('bridge')) {
    return 'Paste a bridge site.'
  }

  if (model.slug.includes('stablecoin')) {
    return 'Paste a stablecoin or issuer site.'
  }

  if (model.slug.includes('nft')) {
    return 'Paste a collection, marketplace, or wallet page.'
  }

  if (model.slug.includes('dex')) {
    return 'Paste a DEX, AMM, or liquidity venue page.'
  }

  return 'Paste a DeFi, governance, or protocol site.'
}

function getModelTargetLabel(model: ModelDefinition) {
  if (model.slug.includes('bridge')) {
    return 'bridge site'
  }

  if (model.slug.includes('stablecoin')) {
    return 'stablecoin page'
  }

  if (model.slug.includes('nft')) {
    return 'NFT market page'
  }

  if (model.slug.includes('dex')) {
    return 'DEX or liquidity page'
  }

  if (model.slug.includes('health')) {
    return 'DeFi protocol page'
  }

  return 'governance or protocol page'
}

function getModelOutputLabel(model: ModelDefinition) {
  if (model.slug.includes('bridge')) {
    return 'bridge risk result'
  }

  if (model.slug.includes('stablecoin')) {
    return 'depeg risk result'
  }

  if (model.slug.includes('nft')) {
    return 'wash trading result'
  }

  if (model.slug.includes('dex')) {
    return 'liquidity exit risk result'
  }

  if (model.slug.includes('health')) {
    return 'protocol health result'
  }

  return 'governance risk result'
}

function getRunLabel(model: ModelDefinition | null) {
  if (!model) {
    return 'Run analysis'
  }

  if (model.slug.includes('bridge')) {
    return 'Run bridge analysis'
  }

  if (model.slug.includes('stablecoin')) {
    return 'Run depeg analysis'
  }

  if (model.slug.includes('nft')) {
    return 'Run NFT analysis'
  }

  if (model.slug.includes('dex')) {
    return 'Run DEX analysis'
  }

  if (model.slug.includes('health')) {
    return 'Run protocol analysis'
  }

  return 'Run governance analysis'
}

function getRunningLabel(model: ModelDefinition | null) {
  if (!model) {
    return 'Running analysis...'
  }

  if (model.slug.includes('bridge')) {
    return 'Scanning bridge...'
  }

  if (model.slug.includes('stablecoin')) {
    return 'Scanning stablecoin...'
  }

  if (model.slug.includes('nft')) {
    return 'Scanning NFT flow...'
  }

  if (model.slug.includes('dex')) {
    return 'Scanning DEX...'
  }

  if (model.slug.includes('health')) {
    return 'Scanning protocol...'
  }

  return 'Scanning governance...'
}

function shortTitle(title: string) {
  return title.replace(/-/g, ' ').replace(/\s+/g, ' ').trim()
}

function normalizePreviewUrl(url: string) {
  const trimmed = url.trim()
  if (!trimmed) {
    return ''
  }

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed
  }

  return `https://${trimmed}`
}

function getHostLabel(url: string) {
  try {
    return new URL(url).host.replace(/^www\./, '')
  } catch {
    return 'protocol site'
  }
}

function sortBridgeEntries(entries: LeaderboardEntry[], sortKey: BridgeSortKey) {
  return [...entries].sort((left, right) => {
    if (sortKey === 'tvl_usd') {
      return Number(right.normalized_input.tvl_usd ?? 0) - Number(left.normalized_input.tvl_usd ?? 0)
    }

    if (sortKey === 'prior_incidents') {
      return Number(right.normalized_input.prior_incidents ?? 0) - Number(left.normalized_input.prior_incidents ?? 0)
    }

    return Number(left.result.risk_score ?? 0) - Number(right.result.risk_score ?? 0)
  })
}

function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime()
  if (!Number.isFinite(timestamp)) {
    return ''
  }

  const diffMs = Date.now() - timestamp
  const diffMinutes = Math.max(1, Math.round(diffMs / 60000))
  if (diffMinutes < 60) {
    return `${diffMinutes}m ago`
  }

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `${diffHours}h ago`
  }

  const diffDays = Math.round(diffHours / 24)
  return `${diffDays}d ago`
}

export default App
