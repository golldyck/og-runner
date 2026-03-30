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

type HealthResponse = {
  status: string
  opengradient_live_ready: boolean
  opengradient_llm_ready?: boolean
}

type WalletPreflightResponse = {
  wallet_address: string | null
  base_sepolia_eth: number | null
  opg_balance: number | null
  permit2_allowance: number | null
  llm_ready: boolean
  live_inference_ready: boolean
  issues: string[]
}

type ProtocolPreviewResponse = {
  url: string
  host: string
  title: string | null
  description: string | null
  image_url: string | null
  site_name: string | null
  embed_allowed: boolean
  status_code: number | null
}

type BridgeSortKey = 'risk_score' | 'tvl_usd' | 'prior_incidents'
type ViewTab = 'runner' | 'protocol' | 'assistant' | 'leaderboard'
type AssistantResponse = {
  answer: string
  source: 'opengradient_llm' | 'local_fallback'
  model_used: string | null
}

type AssistantModelsResponse = {
  current_model: string
  models: string[]
}

const defaultModelRef = 'https://hub.opengradient.ai/models/Goldy/Governance-Capture-Risk-Scorer'
const defaultTargetUrl = ''
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const officialLinks = [
  ['Website', 'https://www.opengradient.ai/'],
  ['Docs', 'https://docs.opengradient.ai/'],
  ['Hub', 'https://hub.opengradient.ai/'],
  ['GitHub', 'https://github.com/OpenGradient'],
  ['MemSync', 'https://www.memsync.ai/'],
  ['Twin', 'https://www.twin.fun/'],
  ['BitQuant', 'https://www.bitquant.io/'],
] as const

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`
}

const fallbackModels: ModelDefinition[] = [
  createFallbackModel({
    slug: 'governance-capture-risk-scorer',
    title: 'Governance Capture Risk Scorer',
    category: 'Governance Risk',
    summary: 'Scores DAO and DeFi governance takeover risk from concentration, execution control, proposal manipulation, and market attack-surface signals.',
    whatItDoes: "Tells you whether a protocol's governance can be captured by whales, insiders, multisig operators, or short-term attackers.",
  }),
  createFallbackModel({
    slug: 'cross-chain-bridge-risk-classifier',
    title: 'Cross-Chain Bridge Risk Classifier',
    category: 'Bridge Risk',
    summary: 'Classifies bridge protocols into LOW, MEDIUM, HIGH, or CRITICAL risk using custody, technical, operational, liquidity, and incident-history signals.',
    whatItDoes: 'Measures how dangerous a bridge design is before a user sends assets through it.',
  }),
  createFallbackModel({
    slug: 'defi-protocol-health-score',
    title: 'DeFi Protocol Health Score',
    category: 'Protocol Health',
    summary: 'Evaluates protocol safety across TVL health, smart contract security, decentralization, market activity, and treasury resilience.',
    whatItDoes: 'Produces a single health score for a DeFi protocol by combining safety, activity, decentralization, and treasury signals.',
  }),
  createFallbackModel({
    slug: 'stablecoin-depeg-risk-monitor',
    title: 'Stablecoin Depeg Risk Monitor',
    category: 'Stablecoin Risk',
    summary: 'Monitors stablecoin peg stress using reserve adequacy, market stress, liquidity depth, and on-chain velocity signals.',
    whatItDoes: 'Warns when a stablecoin is drifting toward a depeg event before the market fully prices it in.',
  }),
  createFallbackModel({
    slug: 'dex-liquidity-exit-risk-scorer',
    title: 'DEX Liquidity Exit Risk Scorer',
    category: 'DEX Liquidity Risk',
    summary: 'Scores how likely a DEX or pool is to lose usable liquidity under LP exits, emissions decay, concentration, and flow stress before traders fully react.',
    whatItDoes: 'Shows whether a DEX or liquidity venue is vulnerable to a sharp liquidity exit before spreads, slippage, and user behavior fully deteriorate.',
  }),
  createFallbackModel({
    slug: 'nft-wash-trading-detector',
    title: 'NFT Wash Trading Detector',
    category: 'NFT Market Integrity',
    summary: 'Scores NFT transactions for wash-trading probability using price, timing, wallet overlap, and wallet history signals.',
    whatItDoes: 'Labels NFT transactions as likely wash trading or legitimate based on suspicious wallet overlap and trading cadence.',
  }),
]

function createFallbackModel({
  slug,
  title,
  category,
  summary,
  whatItDoes,
}: {
  slug: string
  title: string
  category: string
  summary: string
  whatItDoes: string
}): ModelDefinition {
  return {
    slug,
    title,
    owner: 'Goldy',
    hub_url: `https://hub.opengradient.ai/models/Goldy/${title.replaceAll(' ', '-')}`,
    model_cid: 'LOCAL_FALLBACK',
    category,
    summary,
    input_key: 'features',
    input_shape: '[1, N]',
    result_keys: [],
    input_fields: [],
    sample_input: {},
    guide: {
      what_it_does: whatItDoes,
      what_you_need: [],
      what_result_means: [],
      next_steps: [],
    },
  }
}

function resolveFallbackModel(ref: string) {
  const normalized = ref.trim().toLowerCase()
  return fallbackModels.find((item) => {
    return (
      item.slug.toLowerCase() === normalized ||
      item.hub_url.toLowerCase() === normalized ||
      normalized.includes(item.slug.toLowerCase()) ||
      normalized.includes(item.title.toLowerCase().replaceAll(' ', '-'))
    )
  }) ?? null
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
  const [hasUserInteracted, setHasUserInteracted] = useState(false)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [walletPreflight, setWalletPreflight] = useState<WalletPreflightResponse | null>(null)
  const [assistantPrompt, setAssistantPrompt] = useState('')
  const [assistantAnswer, setAssistantAnswer] = useState<string | null>(null)
  const [assistantSource, setAssistantSource] = useState<AssistantResponse['source'] | null>(null)
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [assistantModel, setAssistantModel] = useState('GPT_5_MINI')
  const [assistantModels, setAssistantModels] = useState<string[]>(['GPT_5_MINI'])
  const [protocolPreview, setProtocolPreview] = useState<ProtocolPreviewResponse | null>(null)
  const [protocolPreviewLoading, setProtocolPreviewLoading] = useState(false)
  const modelMenuRef = useRef<HTMLDivElement | null>(null)

  const selectedModelOption = models.some((item) => item.hub_url === modelRef) ? modelRef : '__custom__'
  const hasProtocolUrl = Boolean(normalizePreviewUrl(targetUrl))

  useEffect(() => {
    void loadModels()
    void resolveModel(defaultModelRef, { silent: true })
    void loadGlobalLeaderboard()
    void loadBackendStatus()
    void loadAssistantModels()
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
    const normalizedUrl = normalizePreviewUrl(targetUrl)
    if (!normalizedUrl) {
      setProtocolPreview(null)
      setProtocolPreviewLoading(false)
      return
    }

    const controller = new AbortController()
    setProtocolPreviewLoading(true)

    void fetch(`${apiUrl('/api/protocol/preview')}?url=${encodeURIComponent(normalizedUrl)}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error('Protocol preview failed to load.')
        }
        return (await response.json()) as ProtocolPreviewResponse
      })
      .then((payload) => {
        setProtocolPreview(payload)
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setProtocolPreview(null)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setProtocolPreviewLoading(false)
        }
      })

    return () => controller.abort()
  }, [targetUrl])

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
      setModels(fallbackModels)
    }
  }

  async function resolveModel(ref: string, options?: { silent?: boolean }) {
    setLoadingModel(true)
    if (!options?.silent) {
      setError(null)
    }
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
      const fallbackModel = resolveFallbackModel(ref)
      if (fallbackModel) {
        setModels((current) => (current.length > 0 ? current : fallbackModels))
        setModel(fallbackModel)
      } else {
        setModel(null)
        if (!options?.silent) {
          setError(err instanceof Error ? err.message : 'Unknown resolve error.')
        }
      }
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

  async function loadBackendStatus() {
    try {
      const [healthResponse, walletResponse] = await Promise.all([
        fetch(apiUrl('/health')),
        fetch(apiUrl('/api/wallet/preflight')),
      ])

      if (healthResponse.ok) {
        setHealth((await healthResponse.json()) as HealthResponse)
      }

      if (walletResponse.ok) {
        setWalletPreflight((await walletResponse.json()) as WalletPreflightResponse)
      }
    } catch {
      setHealth(null)
      setWalletPreflight(null)
    }
  }

  async function loadAssistantModels() {
    try {
      const response = await fetch(apiUrl('/api/assistant/models'))
      if (!response.ok) {
        throw new Error('Assistant models failed to load.')
      }
      const payload = (await response.json()) as AssistantModelsResponse
      setAssistantModels(payload.models.length > 0 ? payload.models : ['GPT_5_MINI'])
      setAssistantModel(payload.current_model || 'GPT_5_MINI')
    } catch {
      setAssistantModels(['GPT_5_MINI'])
      setAssistantModel('GPT_5_MINI')
    }
  }

  async function runModel() {
    setHasUserInteracted(true)
    setActiveTab('runner')

    if (!model) {
      setError('Choose a model before running the analysis.')
      return
    }

    if (!targetUrl.trim()) {
      setError('Protocol URL is required.')
      return
    }

    setRunning(true)
    setError(null)
    setRunResult(null)

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
        const failure = await response.text()
        throw new Error(failure || 'Model execution failed.')
      }

      const payload = (await response.json()) as RunResponse
      setRunResult(payload)
      await loadGlobalLeaderboard()
      await loadBackendStatus()
      setLeaderboardFresh(true)

      if (model.slug === 'cross-chain-bridge-risk-classifier') {
        await loadBridgeLeaderboard()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown run error.')
      await loadBackendStatus()
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

                <div className="screen-toprail">
                  <div className="screen-intro">
                    <p className="panel-kicker">OpenGradient model runner</p>
                    <p className="screen-intro-copy">Run Hub-connected models, inspect protocol pages, and explain every score.</p>
                  </div>

                  <div className="official-links">
                    {officialLinks.map(([label, href]) => (
                      <a key={label} className="official-link" href={href} target="_blank" rel="noreferrer">
                        {label}
                      </a>
                    ))}
                  </div>
                </div>

                <div className="view-tabs">
                  {([
                    ['runner', 'Runner'],
                    ...(hasProtocolUrl ? ([['protocol', 'Protocol']] as const) : []),
                    ['assistant', 'Assistant'],
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
                                    setHasUserInteracted(true)
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
                                  setHasUserInteracted(true)
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

                      {model ? (
                        <div className="inline-note inline-note-compact inline-note-tight">
                          <span className="inline-note-key">Model purpose</span>
                          <span>{model.summary}</span>
                          <div className="context-chip-row">
                            <span className="context-chip">Target: {getModelTargetLabel(model)}</span>
                            <span className="context-chip">Output: {getModelOutputLabel(model)}</span>
                          </div>
                        </div>
                      ) : (
                        <div className="inline-note inline-note-compact inline-note-tight">
                          <span className="inline-note-key">Quick start</span>
                          <span>Select a model, paste a protocol URL, and run the analysis.</span>
                        </div>
                      )}

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

                          <div className="inline-note inline-note-compact inline-note-tight">
                            <span className="inline-note-key">Advanced</span>
                            <span>Paste your own model URL, slug, or CID here. This field is only for a custom model reference.</span>
                          </div>

                          <div className="action-row action-row-compact">
                            <button
                              className="screen-button screen-button-muted"
                              onClick={() => {
                                setHasUserInteracted(true)
                                void resolveModel(modelRef)
                              }}
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

                      {model ? (
                        <div className="inline-note inline-note-tight">
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
                          <span>{model.guide.what_it_does}</span>
                          {showGuideDetails ? (
                            <div className="inline-note-details">
                              <p>{model.summary}</p>
                              <p>Input: {model.input_shape}</p>
                              <p>Outputs: {model.result_keys.slice(0, 4).join(', ') || 'Model-specific result fields'}</p>
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      <div className="action-row">
                        <button className="screen-button" onClick={() => void runModel()} disabled={!model || running} type="button">
                          {running ? getRunningLabel(model) : getRunLabel(model)}
                        </button>
                      </div>

                      {error && hasUserInteracted ? <p className="status-line status-line-error">{error}</p> : null}
                      <StatusSummary health={health} walletPreflight={walletPreflight} />
                    </div>

                    <RunnerPreviewPanel model={model} runResult={runResult} targetUrl={targetUrl} protocolPreview={protocolPreview} />
                  </div>
                ) : null}

                {activeTab === 'protocol' && hasProtocolUrl ? (
                  <ProtocolViewport url={targetUrl} preview={protocolPreview} loading={protocolPreviewLoading} />
                ) : null}

                {activeTab === 'assistant' ? (
                  <AssistantTab
                    prompt={assistantPrompt}
                    answer={assistantAnswer}
                    source={assistantSource}
                    loading={assistantLoading}
                    assistantModel={assistantModel}
                    assistantModels={assistantModels}
                    model={model}
                    runResult={runResult}
                    targetUrl={targetUrl}
                    onPromptChange={setAssistantPrompt}
                    onAssistantModelChange={setAssistantModel}
                    onSubmit={async (message) => {
                      setAssistantLoading(true)
                      setAssistantAnswer(null)
                      setAssistantSource(null)
                      setError(null)

                      try {
                        const response = await fetch(apiUrl('/api/assistant'), {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            message,
                            model_ref: modelRef || undefined,
                            llm_model: assistantModel,
                            target_url: normalizePreviewUrl(targetUrl) || undefined,
                            result: runResult?.result ?? {},
                          }),
                        })

                        if (!response.ok) {
                          throw new Error('Assistant did not return an answer.')
                        }

                        const payload = (await response.json()) as AssistantResponse
                        setAssistantAnswer(payload.answer)
                        setAssistantSource(payload.source)
                        if (payload.model_used) {
                          setAssistantModel(payload.model_used)
                        }
                        await loadBackendStatus()
                      } catch (err) {
                        setAssistantAnswer(
                          buildLocalAssistantFallback({
                            message,
                            model,
                            runResult,
                            targetUrl,
                          }),
                        )
                        setAssistantSource('local_fallback')
                        setError(err instanceof Error ? err.message : 'Assistant request failed.')
                      } finally {
                        setAssistantLoading(false)
                      }
                    }}
                  />
                ) : null}

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

function StatusSummary({
  health,
  walletPreflight,
}: {
  health: HealthResponse | null
  walletPreflight: WalletPreflightResponse | null
}) {
  if (!health && !walletPreflight) {
    return null
  }

  const liveReady = Boolean(health?.opengradient_live_ready && walletPreflight?.live_inference_ready)
  const llmReady = Boolean(health?.opengradient_llm_ready && walletPreflight?.llm_ready)
  const issues = walletPreflight?.issues ?? []

  return (
    <div className="inline-note inline-note-tight status-summary">
      <span className="inline-note-key">Live status</span>
      <div className="context-chip-row">
        <span className={`context-chip ${liveReady ? 'context-chip-ok' : 'context-chip-warn'}`}>
          {liveReady ? 'Inference live' : 'Inference fallback'}
        </span>
        <span className={`context-chip ${llmReady ? 'context-chip-ok' : 'context-chip-warn'}`}>
          {llmReady ? 'LLM live' : 'LLM fallback'}
        </span>
      </div>
      {walletPreflight?.wallet_address ? (
        <span className="status-summary-copy">
          Wallet {shortWallet(walletPreflight.wallet_address)} · ETH {formatCompactNumber(walletPreflight.base_sepolia_eth)} · OPG{' '}
          {formatCompactNumber(walletPreflight.opg_balance)}
        </span>
      ) : null}
      <span className="status-summary-copy">{getLiveStatusCopy(liveReady, llmReady, issues)}</span>
    </div>
  )
}

function SiteBackdrop({ url }: { url: string }) {
  const normalizedUrl = normalizePreviewUrl(url)
  const host = getHostLabel(normalizedUrl)
  const proxiedUrl = normalizedUrl ? `${apiUrl('/api/protocol/render')}?url=${encodeURIComponent(normalizedUrl)}` : ''

  if (!normalizedUrl) {
    return null
  }

  return (
    <div className="site-backdrop">
      <div className="site-backdrop-frame">
        <iframe
          title="site-preview"
          src={proxiedUrl}
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
            <ScoreBadge score={String(entry.result.risk_score ?? '-')} label={String(entry.result.risk_category ?? '-')} />
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
                  <span className="activity-tag">{entry.source === 'user' ? 'User run' : 'Curated'}</span>
                </div>
              </div>
              <div className="activity-side">
                <ScoreBadge score={entry.headline_score} label={entry.headline_label} />
                <span className="activity-time">{entry.created_at ? formatRelativeTime(entry.created_at) : 'saved'}</span>
              </div>
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
  protocolPreview,
}: {
  model: ModelDefinition | null
  runResult: RunResponse | null
  targetUrl: string
  protocolPreview: ProtocolPreviewResponse | null
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

            {!protocolPreview?.embed_allowed && targetUrl ? (
              <div className="protocol-hint-card">
                <p className="panel-kicker">Protocol source</p>
                <p className="protocol-hint-copy">
                  This site blocks direct embedding, so the runner is showing a proxied static preview of the protocol page.
                </p>
              </div>
            ) : null}

            {summarizeWarnings(runResult.warnings).length > 0 ? (
              <div className="status-line">
                {summarizeWarnings(runResult.warnings).map((warning) => (
                  <p key={warning} className="status-line-copy">
                    {warning}
                  </p>
                ))}
              </div>
            ) : null}
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

function ProtocolViewport({
  url,
  preview,
  loading,
}: {
  url: string
  preview: ProtocolPreviewResponse | null
  loading: boolean
}) {
  const embedBlocked = preview ? !preview.embed_allowed : false

  return (
    <div className="protocol-shell">
      <div className="screen-output screen-preview-panel protocol-panel">
        <SiteBackdrop url={url} />
        <div className="preview-shade" />
        <div className="preview-content protocol-panel-copy">
          <div className="protocol-panel-note">
            <p className="panel-kicker">Protocol</p>
            <p>
              {embedBlocked
                ? 'This protocol blocks direct embedding, so the runner is showing a proxied static preview instead.'
                : 'This panel shows the live protocol page the model is analyzing in the background.'}
            </p>
          </div>
        </div>
      </div>

      <div className="protocol-preview-card">
        <p className="panel-kicker">Protocol preview</p>
        {loading ? (
          <p className="protocol-preview-copy">Loading protocol metadata...</p>
        ) : (
          <>
            <div className="protocol-preview-head">
              <div>
                <strong>{preview?.title ?? getHostLabel(normalizePreviewUrl(url))}</strong>
                <span>{preview?.site_name ?? preview?.host ?? getHostLabel(normalizePreviewUrl(url))}</span>
              </div>
              <div className="context-chip-row">
                <span className={`context-chip ${embedBlocked ? 'context-chip-warn' : 'context-chip-ok'}`}>
                  {embedBlocked ? 'Static preview' : 'Live preview'}
                </span>
              </div>
            </div>

            {preview?.image_url ? <img className="protocol-preview-image" src={preview.image_url} alt={preview.title ?? 'Protocol preview'} /> : null}

            <p className="protocol-preview-copy">
              {preview?.description ?? 'Open the live protocol page in a separate tab if the site blocks embedding inside the runner.'}
            </p>

            <div className="protocol-preview-actions">
              <a className="screen-button protocol-preview-button" href={normalizePreviewUrl(url)} target="_blank" rel="noreferrer">
                Open protocol
              </a>
              <span className="protocol-preview-host">{preview?.host ?? getHostLabel(normalizePreviewUrl(url))}</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function getScoreTone(label: string | null | undefined) {
  const normalized = String(label ?? '').toLowerCase()
  if (normalized.includes('critical') || normalized.includes('grade f') || normalized.includes('grade d') || normalized.includes('warning')) {
    return 'score-badge-negative'
  }
  if (normalized.includes('high') || normalized.includes('medium') || normalized.includes('grade c') || normalized.includes('grade b') || normalized.includes('watch')) {
    return 'score-badge-warn'
  }
  return 'score-badge-positive'
}

function ScoreBadge({
  score,
  label,
}: {
  score: string | null | undefined
  label: string | null | undefined
}) {
  const tone = getScoreTone(label)

  return (
    <div className="score-badge-stack">
      <span className={`score-badge-value ${tone}`}>{score ?? '-'}</span>
      <span className={`score-badge-label ${tone}`}>{label ?? '-'}</span>
    </div>
  )
}

function AssistantTab({
  prompt,
  answer,
  source,
  loading,
  assistantModel,
  assistantModels,
  model,
  runResult,
  targetUrl,
  onPromptChange,
  onAssistantModelChange,
  onSubmit,
}: {
  prompt: string
  answer: string | null
  source: AssistantResponse['source'] | null
  loading: boolean
  assistantModel: string
  assistantModels: string[]
  model: ModelDefinition | null
  runResult: RunResponse | null
  targetUrl: string
  onPromptChange: (value: string) => void
  onAssistantModelChange: (value: string) => void
  onSubmit: (message: string) => Promise<void>
}) {
  const suggestions = buildAssistantSuggestions(model, runResult, targetUrl)

  return (
    <div className="assistant-shell">
      <div className="assistant-panel">
        <div className="assistant-head">
          <div>
            <p className="panel-kicker">OpenGradient assistant</p>
            <h3>Ask the runner what a model does, what to paste, and how to read the result.</h3>
          </div>
          <div className="context-chip-row">
            <span className={`context-chip ${source === 'opengradient_llm' ? 'context-chip-ok' : 'context-chip-warn'}`}>
              {source === 'opengradient_llm' ? 'LLM live' : 'Assistant ready'}
            </span>
          </div>
        </div>

        <div className="assistant-prompt-row">
          <label className="field-shell">
            <span className="field-label">OpenGradient LLM</span>
            <select className="screen-input assistant-model-select" value={assistantModel} onChange={(event) => onAssistantModelChange(event.target.value)}>
              {assistantModels.map((item) => (
                <option key={item} value={item}>
                  {formatLlmModelLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <textarea
            className="screen-input assistant-input"
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="Ask about a model, a protocol URL, or the latest score."
          />
          <button
            className="screen-button"
            onClick={() => void onSubmit((prompt || suggestions[0]).trim())}
            disabled={loading}
            type="button"
          >
            {loading ? 'Thinking...' : 'Ask assistant'}
          </button>
        </div>

        <div className="assistant-suggestions">
          {suggestions.map((suggestion) => (
            <button key={suggestion} className="choice-chip" onClick={() => onPromptChange(suggestion)} type="button">
              {suggestion}
            </button>
          ))}
        </div>

        <div className="assistant-context-grid">
          <div className="inline-note inline-note-tight">
            <span className="inline-note-key">Current model</span>
            <span>{model ? `${shortTitle(model.title)} · ${model.category}` : 'Choose a model to ground the assistant.'}</span>
          </div>
          <div className="inline-note inline-note-tight">
            <span className="inline-note-key">Current target</span>
            <span>{targetUrl ? getHostLabel(normalizePreviewUrl(targetUrl)) : 'Paste a protocol page to add site context.'}</span>
          </div>
          <div className="inline-note inline-note-tight">
            <span className="inline-note-key">Current result</span>
            <span>{runResult && model ? `${getHeadlineScore(model, runResult.result)} · ${getScoreMeta(model, runResult.result)}` : 'Run a model to ask about the score.'}</span>
          </div>
        </div>
      </div>

      <div className="assistant-panel assistant-answer-panel">
        <p className="panel-kicker">Assistant output</p>
        {answer ? (
          <>
            <AssistantAnswerPanel answer={answer} model={model} runResult={runResult} targetUrl={targetUrl} />
            <div className="context-chip-row">
              <span className={`context-chip ${source === 'opengradient_llm' ? 'context-chip-ok' : 'context-chip-warn'}`}>
                {source === 'opengradient_llm' ? 'Powered by OpenGradient LLM' : 'Using local fallback'}
              </span>
              <span className="context-chip">{formatLlmModelLabel(assistantModel)}</span>
            </div>
          </>
        ) : (
          <div className="empty-state assistant-empty-state">
            <p className="panel-kicker">Ready</p>
            <p>The assistant can explain what each model measures, suggest the right protocol page, and translate the score into plain English.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function AssistantAnswerPanel({
  answer,
  model,
  runResult,
  targetUrl,
}: {
  answer: string
  model: ModelDefinition | null
  runResult: RunResponse | null
  targetUrl: string
}) {
  const sections = buildAssistantSections(answer, model, runResult, targetUrl)

  return (
    <div className="assistant-answer-grid">
      {sections.map((section) => (
        <div key={section.label} className="assistant-answer-card">
          <p className="panel-kicker">{section.label}</p>
          <p className="assistant-answer">{section.copy}</p>
        </div>
      ))}
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

function summarizeWarnings(warnings: string[]) {
  const messages = warnings.map((warning) => {
    const normalized = warning.toLowerCase()
    if (normalized.includes('live opengradient inference failed')) {
      return 'Live OpenGradient inference is temporarily unavailable. Showing a validated local fallback result.'
    }
    if (normalized.includes('live opengradient inference is currently disabled')) {
      return 'Live OpenGradient inference is disabled right now, so the runner is using the fast local analysis path.'
    }
    if (normalized.includes('llm') && normalized.includes('fallback')) {
      return 'The score explanation is currently using local fallback copy instead of the OpenGradient LLM.'
    }
    if (normalized.includes('llm explanations are currently disabled')) {
      return 'The score explanation is using local fallback copy because OpenGradient LLM mode is currently disabled.'
    }
    if (normalized.includes('heuristic') || normalized.includes('demo')) {
      return 'This result is based on a fallback extraction path, so it should be treated as directional rather than final.'
    }

    return warning
  })

  return [...new Set(messages)]
}

function getLiveStatusCopy(liveReady: boolean, llmReady: boolean, issues: string[]) {
  if (liveReady && llmReady) {
    return 'Wallet, inference, and assistant routes are ready for OpenGradient live execution.'
  }

  if (issues.length > 0) {
    return issues[0]
  }

  if (!liveReady && !llmReady) {
    return 'OpenGradient live routes are not fully available right now. The runner will stay usable with local fallback modes.'
  }

  if (!liveReady) {
    return 'Inference is currently falling back to the local path while wallet and Hub context stay available.'
  }

  return 'The assistant is currently falling back to local copy while inference stays available.'
}

function buildLocalAssistantFallback({
  message,
  model,
  runResult,
  targetUrl,
}: {
  message: string
  model: ModelDefinition | null
  runResult: RunResponse | null
  targetUrl: string
}) {
  const normalizedMessage = message.trim().toLowerCase()
  const host = targetUrl ? getHostLabel(normalizePreviewUrl(targetUrl)) : null

  if (model && (normalizedMessage.includes('what') || normalizedMessage.includes('model') || normalizedMessage.includes('measure'))) {
    return `${shortTitle(model.title)} measures ${model.summary} ${model.guide.what_it_does}`
  }

  if (model && host && !runResult) {
    return `Use ${shortTitle(model.title)} for ${host}. Paste the protocol page, run the analysis, and the runner will return ${getModelOutputLabel(model).toLowerCase()} plus the main parameter scales.`
  }

  if (model && runResult) {
    return `${shortTitle(model.title)} scored ${getHeadlineScore(model, runResult.result)} for ${host ?? 'the current target'}, with verdict ${getScoreMeta(model, runResult.result)}. The strongest visible drivers are shown in the parameter scales and detail cards in the Runner tab.`
  }

  if (normalizedMessage.includes('bridge')) {
    return 'Use Cross-Chain Bridge Risk Classifier for bridge pages. It scores custody risk, technical verification, operations, liquidity design, and incident history.'
  }

  if (normalizedMessage.includes('stablecoin') || normalizedMessage.includes('depeg')) {
    return 'Use Stablecoin Depeg Risk Monitor for stablecoin or issuer pages. It focuses on reserve adequacy, market stress, liquidity depth, and on-chain velocity.'
  }

  if (normalizedMessage.includes('dex') || normalizedMessage.includes('liquidity')) {
    return 'Use DEX Liquidity Exit Risk Scorer for DEX or AMM pages. It evaluates LP concentration, emissions dependence, flow stress, and slippage resilience.'
  }

  if (normalizedMessage.includes('nft')) {
    return 'Use NFT Wash Trading Detector for collection, marketplace, or wallet pages. It flags suspicious wallet overlap and trading cadence.'
  }

  return 'The assistant is using local fallback right now. Choose a model, paste a protocol URL, and ask what the model measures, what page to use, or why the current score was assigned.'
}

function buildAssistantSections(
  answer: string,
  model: ModelDefinition | null,
  runResult: RunResponse | null,
  targetUrl: string,
) {
  const sections: { label: string; copy: string }[] = []
  const host = targetUrl ? getHostLabel(normalizePreviewUrl(targetUrl)) : null

  if (model) {
    sections.push({
      label: 'What it does',
      copy: `${shortTitle(model.title)} measures ${model.summary}`,
    })
  }

  if (host) {
    sections.push({
      label: 'Current target',
      copy: `The current protocol context is ${host}. Use the protocol page that best represents the product, governance, bridge, or market surface you want scored.`,
    })
  }

  if (model && runResult) {
    sections.push({
      label: 'Current read',
      copy: `${shortTitle(model.title)} scored ${getHeadlineScore(model, runResult.result)} with verdict ${getScoreMeta(model, runResult.result)} for ${host ?? 'the current target'}. Review the parameter scales to see the strongest drivers.`,
    })
  }

  sections.push({
    label: 'Assistant note',
    copy: answer,
  })

  return sections
}

function buildAssistantSuggestions(
  model: ModelDefinition | null,
  runResult: RunResponse | null,
  targetUrl: string,
) {
  const host = targetUrl ? getHostLabel(normalizePreviewUrl(targetUrl)) : null
  const suggestions: string[] = []

  if (!model) {
    return [
      'Help me choose the right OpenGradient model.',
      'Find a model for bridge, DEX, or stablecoin risk.',
      'Which protocol page should I paste for the cleanest analysis?',
    ]
  }

  suggestions.push(`Explain what ${shortTitle(model.title)} is measuring.`)

  if (host) {
    suggestions.push(`Which ${getModelTargetLabel(model)} should I use for ${host}?`)
  } else {
    suggestions.push(`Which ${getModelTargetLabel(model)} should I paste for the cleanest run?`)
  }

  if (runResult) {
    suggestions.push(`Why did ${shortTitle(model.title)} return ${getHeadlineScore(model, runResult.result)} and ${getScoreMeta(model, runResult.result)}?`)
  }

  if (model.slug.includes('bridge')) {
    suggestions.push(host ? `What makes ${host} safer or riskier as a bridge?` : 'Which bridge design signals matter most: custody, timelock, verification, or incidents?')
  } else if (model.slug.includes('governance')) {
    suggestions.push(host ? `What governance weaknesses should I check first on ${host}?` : 'Which governance signals matter most: concentration, quorum fragility, insider control, or flashloan exposure?')
  } else if (model.slug.includes('stablecoin')) {
    suggestions.push(host ? `What depeg triggers should I watch first on ${host}?` : 'Which stablecoin signals matter most: reserves, liquidity, market stress, or on-chain velocity?')
  } else if (model.slug.includes('dex')) {
    suggestions.push(host ? `What liquidity exit risks should I check first on ${host}?` : 'Which DEX signals matter most: LP concentration, emissions dependence, slippage, or whale exits?')
  } else if (model.slug.includes('nft')) {
    suggestions.push(host ? `What wash trading signals should I inspect first on ${host}?` : 'Which NFT signals matter most: wallet overlap, timing, prior activity, or price behavior?')
  } else if (model.slug.includes('health')) {
    suggestions.push(host ? `What protocol health risks should I inspect first on ${host}?` : 'Which protocol health pillars matter most: TVL health, security, decentralization, activity, or treasury?')
  }

  return [...new Set(suggestions)].slice(0, 4)
}

function formatLlmModelLabel(value: string) {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => (part.length <= 3 ? part.toUpperCase() : `${part[0]}${part.slice(1).toLowerCase()}`))
    .join(' ')
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

function shortWallet(value: string) {
  return `${value.slice(0, 6)}...${value.slice(-4)}`
}

function formatCompactNumber(value: number | null) {
  if (value == null || Number.isNaN(value)) {
    return '-'
  }

  if (value >= 1000) {
    return `${Math.round(value)}`
  }

  if (value >= 1) {
    return value.toFixed(2)
  }

  return value.toFixed(4)
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
