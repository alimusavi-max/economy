import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import {
  Area, AreaChart, Brush, CartesianGrid, ComposedChart,
  Legend, Line, ReferenceLine, ResponsiveContainer, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis
} from 'recharts'
import {
  Activity, AlertCircle, AlertTriangle, Bell, CheckCircle, Clock,
  Database, Download, FlaskConical, Info, LogOut, Maximize2,
  Minimize2, RefreshCcw, Search, SlidersHorizontal, TrendingDown,
  TrendingUp, UserPlus, Users, WandSparkles
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const ACTIVE_USER_STORAGE_KEY = 'economy_active_user_id'
const MAX_DASHBOARD_SYMBOLS = 12

const CHART_RANGES = [
  { key: '1M', label: '۱ ماه', days: 31 },
  { key: '3M', label: '۳ ماه', days: 93 },
  { key: '1Y', label: '۱ سال', days: 366 },
  { key: '5Y', label: '۵ سال', days: 1825 },
  { key: 'ALL', label: 'کل', days: Infinity },
]

const SOURCE_CONFIGS = [
  { key: 'FRED',         label: 'FRED',         desc: 'فدرال رزرو آمریکا',          discoverPath: '/discover/auto-spider?source=FRED',      color: '#3b82f6', interval: '۳۰ روز' },
  { key: 'WORLDBANK',    label: 'World Bank',    desc: 'بانک جهانی (۲۶۶ کشور)',      discoverPath: '/discover/auto-spider?source=WORLDBANK',  color: '#22c55e', interval: '۱۸۰ روز' },
  { key: 'IMF',          label: 'IMF',           desc: 'صندوق بین‌المللی پول',        discoverPath: '/discover/imf',                           color: '#a855f7', interval: '۹۰ روز' },
  { key: 'OECD',         label: 'OECD',          desc: 'سازمان همکاری اقتصادی',      discoverPath: '/discover/oecd',                          color: '#f97316', interval: '۳۰ روز' },
  { key: 'BIS',          label: 'BIS',           desc: 'تسویه‌حساب بین‌المللی',       discoverPath: '/discover/bis',                           color: '#ef4444', interval: '۳۰ روز' },
  { key: 'ECB',          label: 'ECB',           desc: 'بانک مرکزی اروپا',           discoverPath: '/discover/auto-spider?source=ECB',        color: '#eab308', interval: '۳۰ روز' },
  { key: 'EUROSTAT',     label: 'Eurostat',      desc: 'مرکز آمار اتحادیه اروپا',    discoverPath: '/discover/eurostat',                      color: '#6366f1', interval: '۳۰ روز' },
  { key: 'DBNOMICS',     label: 'DB.NOMICS',     desc: '۹۰+ بانک مرکزی دنیا',        discoverPath: '/discover/dbnomics',                      color: '#d946ef', interval: '۱۵ روز' },
  { key: 'YAHOO',        label: 'Yahoo Finance', desc: 'سهام، فارکس، کریپتو',        discoverPath: '/discover/market-seed',                   color: '#06b6d4', interval: '۱ روز' },
  { key: 'ALPHAVANTAGE', label: 'Alpha Vantage', desc: 'بازارهای مالی',              discoverPath: null,                                      color: '#f43f5e', interval: '۱ روز' },
  { key: 'ILO',          label: 'ILO',           desc: 'سازمان بین‌المللی کار',       discoverPath: '/discover/ilo',                           color: '#14b8a6', interval: '۹۰ روز' },
  { key: 'FAO',          label: 'FAO',           desc: 'خواربار و کشاورزی ملل',       discoverPath: '/discover/fao',                           color: '#84cc16', interval: '۱۸۰ روز' },
  { key: 'UN',           label: 'UN Data',       desc: 'سازمان ملل متحد (SDG)',       discoverPath: '/discover/un',                            color: '#0ea5e9', interval: '۹۰ روز' },
  { key: 'TREASURY',     label: 'US Treasury',   desc: 'خزانه‌داری ایالات متحده',     discoverPath: '/discover/treasury',                      color: '#f59e0b', interval: '۳۰ روز' },
]

const SOURCE_COLOR_MAP = Object.fromEntries(SOURCE_CONFIGS.map(s => [s.key, s.color]))

const FORMULA_TEMPLATES = [
  { label: 'تورم واقعی YoY%', formula: 'pct_change(A, 12)', hint: 'A = شاخص قیمت ماهانه' },
  { label: 'نرخ واقعی بهره', formula: 'A - B', hint: 'A = نرخ اسمی، B = تورم' },
  { label: 'نسبت به GDP', formula: 'A / B * 100', hint: 'A = متغیر، B = GDP' },
  { label: 'سرعت گردش پول', formula: 'A / B', hint: 'A = GDP، B = نقدینگی' },
  { label: 'MA-12', formula: 'rolling_mean(A, 12)', hint: 'A = سری ماهانه' },
  { label: 'MA-4', formula: 'rolling_mean(A, 4)', hint: 'A = سری فصلی' },
  { label: 'Z-Score', formula: 'zscore(A)', hint: 'A = هر سری' },
  { label: 'نرمال ۰-۱۰۰', formula: 'normalize(A)', hint: 'A = هر سری' },
  { label: 'Log', formula: 'log(A)', hint: 'A = هر سری مثبت' },
  { label: 'تغییر مطلق', formula: 'diff(A, 1)', hint: 'A = هر سری' },
  { label: 'ضرب', formula: 'A * B', hint: 'A، B = دو شاخص' },
  { label: 'جمع', formula: 'A + B', hint: 'A، B = دو شاخص' },
  { label: 'مجموع تجمعی', formula: 'cumsum(A)', hint: 'A = هر سری' },
  { label: 'STD-12', formula: 'rolling_std(A, 12)', hint: 'A = سری ماهانه' },
  { label: 'تغییر ۳ماهه', formula: 'pct_change(A, 3)', hint: 'A = سری ماهانه' },
]

const SERIES_COLORS = ['#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#facc15']

// ── helpers ──────────────────────────────────────────────
const extractErrorMessage = (err, fallback) =>
  err?.response?.data?.detail || err?.message || fallback

const fmt = (v) =>
  Intl.NumberFormat('fa-IR', { notation: 'compact', maximumFractionDigits: 2 }).format(v || 0)

const fmtFull = (v) =>
  Intl.NumberFormat('fa-IR', { maximumFractionDigits: 4 }).format(v || 0)

const sourceSupportsRefresh = (s) =>
  ['FRED','YAHOO','WORLDBANK','ECB','DBNOMICS','IMF','OECD','BIS',
   'EUROSTAT','ALPHAVANTAGE','ILO','TREASURY','FAO','UN'].includes(s)

const withRetry = async (fn, retries = 1) => {
  let last
  for (let i = 0; i <= retries; i++) { try { return await fn() } catch (e) { last = e } }
  throw last
}

const filterByRange = (data, rangeKey) => {
  const range = CHART_RANGES.find(r => r.key === rangeKey) || CHART_RANGES.at(-1)
  if (!data?.length || !Number.isFinite(range.days)) return data || []
  const lastTs = new Date(data[data.length - 1].date).getTime()
  const minTs = lastTs - range.days * 86400000
  return data.filter(d => new Date(d.date).getTime() >= minTs)
}

const exportCSV = (data, filename) => {
  if (!data?.length) return
  const csv = ['date,value', ...data.map(d => `${d.date},${d.value}`)].join('\n')
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: `${filename}.csv`,
  })
  a.click(); URL.revokeObjectURL(a.href)
}

const getDelta = (data) => {
  if (!data || data.length < 2) return null
  const cur = data[data.length - 1]?.value
  const prev = data[data.length - 2]?.value
  if (cur == null || !prev) return null
  return ((cur - prev) / Math.abs(prev)) * 100
}

// ── shared components ─────────────────────────────────────
function SourceBadge({ source }) {
  const color = SOURCE_COLOR_MAP[source] || '#64748b'
  return (
    <span style={{ background: color + '22', color, border: `1px solid ${color}44` }}
          className="text-[10px] px-1.5 py-0.5 rounded font-mono font-medium leading-none">
      {source}
    </span>
  )
}

function Toast({ msg, onDismiss }) {
  if (!msg?.text) return null
  const cfg = {
    success: { wrap: 'bg-emerald-900/90 border-emerald-600', Icon: CheckCircle, ic: 'text-emerald-400' },
    error:   { wrap: 'bg-rose-900/90 border-rose-600',       Icon: AlertCircle,   ic: 'text-rose-400' },
    warning: { wrap: 'bg-amber-900/90 border-amber-600',     Icon: AlertTriangle, ic: 'text-amber-400' },
    info:    { wrap: 'bg-sky-900/90 border-sky-600',         Icon: Info,          ic: 'text-sky-400' },
  }
  const { wrap, Icon, ic } = cfg[msg.type] || cfg.info
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-sm shadow-xl ${wrap}`}>
      <Icon size={15} className={`shrink-0 ${ic}`} />
      <span className="flex-1 text-slate-100">{msg.text}</span>
      <button onClick={onDismiss} className="text-slate-400 hover:text-white text-lg leading-none">×</button>
    </div>
  )
}

function StatCard({ title, value, Icon, color = '#38bdf8', sub }) {
  return (
    <div className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4 relative overflow-hidden">
      <div className="absolute inset-0 opacity-[0.04] rounded-xl"
           style={{ background: `radial-gradient(circle at top left, ${color}, transparent 70%)` }} />
      <div className="relative">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">{title}</span>
          {Icon && <Icon size={13} style={{ color }} className="opacity-60" />}
        </div>
        <div className="text-2xl font-bold" style={{ color }}>{value != null ? fmt(value) : '—'}</div>
        {sub && <div className="text-[10px] text-slate-600 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

function MiniChart({ data, color, showStats }) {
  if (!data?.length) return (
    <div className="h-16 flex items-center justify-center text-xs text-slate-700">بدون داده</div>
  )
  const last = data.at(-1)?.value
  const first = data[0]?.value
  const pctChange = first && first !== 0 ? ((last - first) / Math.abs(first)) * 100 : null
  return (
    <div className="space-y-0.5">
      {showStats && last != null && (
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-400 font-mono">{fmtFull(last)}</span>
          {pctChange != null && (
            <span className={pctChange >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
              {pctChange >= 0 ? '+' : ''}{pctChange.toFixed(1)}%
            </span>
          )}
        </div>
      )}
      <div className="h-14">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <Area dataKey="value" stroke={color} fill={`${color}22`} dot={false} strokeWidth={1.5} />
            <Tooltip formatter={fmtFull} contentStyle={{ background: '#0f172a', border: 'none', fontSize: 11 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────
export default function App() {
  const [summary, setSummary] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [loading, setLoading] = useState(false)
  const [_msg, _setMsg] = useState(null)

  const _msgTimerRef = useRef(null)
  const setMessage = useCallback((textOrObj, type = 'info') => {
    if (!textOrObj) { _setMsg(null); return }
    _setMsg(typeof textOrObj === 'string' ? { text: textOrObj, type } : textOrObj)
    if (_msgTimerRef.current) clearTimeout(_msgTimerRef.current)
    if (type !== 'error') {
      _msgTimerRef.current = setTimeout(() => _setMsg(null), 6000)
    }
  }, [])

  const [recentActivity, setRecentActivity] = useState([])
  const [topSeries, setTopSeries] = useState([])
  const [activeTab, setActiveTab] = useState('dashboard')
  const [quickSearchOpen, setQuickSearchOpen] = useState(false)
  const [quickSearchQuery, setQuickSearchQuery] = useState('')
  const [quickSearchResults, setQuickSearchResults] = useState([])
  const [quickSearchLoading, setQuickSearchLoading] = useState(false)
  const quickSearchTimer = useRef(null)
  const [notifOpen, setNotifOpen] = useState(false)
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(0) // minutes; 0 = off
  const [sourceFilter, setSourceFilter] = useState('')
  const [dbnomicsProviderFilter, setDbnomicsProviderFilter] = useState('')
  const [dbnomicsProviderSearch, setDbnomicsProviderSearch] = useState('')
  const [dbnomicsProviders, setDbnomicsProviders] = useState([])
  const [search, setSearch] = useState('')
  const [withDataOnly, setWithDataOnly] = useState(false)
  const [sortBy, setSortBy] = useState('source')
  const [sortDir, setSortDir] = useState('asc')
  const [symbolsPage, setSymbolsPage] = useState(1)
  const [symbolsPageSize, setSymbolsPageSize] = useState(100)
  const [symbolsTotalPages, setSymbolsTotalPages] = useState(1)
  const [symbolsTotal, setSymbolsTotal] = useState(0)
  const [selectedSymbols, setSelectedSymbols] = useState([])
  const [tagFilter, setTagFilter] = useState('')
  const [pinnedSymbols, setPinnedSymbols] = useState(() => {
    try { return JSON.parse(localStorage.getItem('pinned_symbols') || '[]') } catch { return [] }
  })

  const togglePin = (sym) => {
    setPinnedSymbols(p => {
      const next = p.includes(sym) ? p.filter(s => s !== sym) : [...p, sym]
      localStorage.setItem('pinned_symbols', JSON.stringify(next))
      return next
    })
  }

  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [loginUserId, setLoginUserId] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [defaultDashboardSymbols, setDefaultDashboardSymbols] = useState([])
  const [dashboardCharts, setDashboardCharts] = useState([])
  const [dashboardRanges, setDashboardRanges] = useState({})

  const [expandedOpen, setExpandedOpen] = useState(false)
  const [expandedSym, setExpandedSym] = useState('')
  const [expandedTableMode, setExpandedTableMode] = useState(false)
  const [expandedData, setExpandedData] = useState([])
  const [expandedRange, setExpandedRange] = useState('ALL')
  const [expandedSym2, setExpandedSym2] = useState('')
  const [expandedData2, setExpandedData2] = useState([])

  const [backendOk, setBackendOk] = useState(null)

  const activeUser = useMemo(() =>
    users.find(u => String(u.id) === String(selectedUserId)) || null,
    [users, selectedUserId])
  const isLoggedIn = !!activeUser

  // ── loaders ──
  const fetchChart = useCallback(async (symbol) => {
    const r = await withRetry(() => axios.get(`${API_BASE}/data/${symbol}`), 1)
    return r.data?.data || []
  }, [])

  const loadUsers = useCallback(async () => {
    const res = await axios.get(`${API_BASE}/users`)
    const all = res.data || []
    setUsers(all)
    const stored = localStorage.getItem(ACTIVE_USER_STORAGE_KEY)
    if (stored && all.some(u => String(u.id) === stored)) {
      setSelectedUserId(stored); setLoginUserId(stored); return
    }
    if (!stored && !loginUserId && all.length) {
      const id = String(all[0].id)
      setLoginUserId(id)
      if (!selectedUserId) setSelectedUserId(id)
    }
  }, [loginUserId, selectedUserId])

  const loadDbnomicsProviders = useCallback(async () => {
    if (sourceFilter !== 'DBNOMICS') return
    try {
      const params = { limit: 20000 }
      if (dbnomicsProviderSearch.trim()) params.search = dbnomicsProviderSearch.trim()
      if (withDataOnly) params.with_data_only = true
      const r = await axios.get(`${API_BASE}/data/dbnomics/providers`, { params })
      setDbnomicsProviders(r.data || [])
    } catch { setDbnomicsProviders([]) }
  }, [dbnomicsProviderSearch, sourceFilter, withDataOnly])

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const params = { paginated: true, page: symbolsPage, page_size: symbolsPageSize, limit: 10000,
                       sort_by: sortBy, sort_dir: sortDir }
      if (sourceFilter) params.source = sourceFilter
      if (dbnomicsProviderFilter && sourceFilter === 'DBNOMICS') params.dbnomics_provider = dbnomicsProviderFilter
      if (search.trim()) params.search = search.trim()
      if (withDataOnly) params.with_data_only = true

      const [sumR, fresR, symR, actR, topR] = await Promise.allSettled([
        axios.get(`${API_BASE}/data/summary`),
        axios.get(`${API_BASE}/data/freshness`),
        axios.get(`${API_BASE}/data/symbols/available`, { params }),
        axios.get(`${API_BASE}/data/recent-activity`, { params: { limit: 8 } }),
        axios.get(`${API_BASE}/data/top-series`, { params: { limit: 6 } }),
      ])
      if (sumR.status === 'fulfilled') setSummary(sumR.value.data)
      if (fresR.status === 'fulfilled') setFreshness(fresR.value.data)
      if (actR.status === 'fulfilled') setRecentActivity(actR.value.data || [])
      if (topR.status === 'fulfilled') setTopSeries(topR.value.data || [])
      if (symR.status === 'fulfilled') {
        setSymbols(symR.value.data?.items || [])
        setSymbolsTotal(symR.value.data?.pagination?.total || 0)
        setSymbolsTotalPages(symR.value.data?.pagination?.total_pages || 1)
      } else { setSymbols([]) }
      setSelectedSymbols([])
      setBackendOk(symR.status === 'fulfilled')
    } catch (err) {
      setBackendOk(false); setSummary(null); setFreshness(null); setSymbols([])
      setMessage(extractErrorMessage(err, 'خطا در بارگذاری داشبورد.'), 'error')
    } finally { setLoading(false) }
  }, [dbnomicsProviderFilter, search, sortBy, sortDir, sourceFilter, symbolsPage, symbolsPageSize, withDataOnly, setMessage])

  const loadUserDashboard = useCallback(async (userId) => {
    if (!userId) return
    try {
      const r = await axios.get(`${API_BASE}/users/${userId}/dashboard`)
      const syms = r.data?.symbols || []
      setDefaultDashboardSymbols(syms)
      const charts = await Promise.all(
        syms.slice(0, MAX_DASHBOARD_SYMBOLS).map(async sym => {
          try { return { symbol: sym, data: await fetchChart(sym), error: null } }
          catch (e) { return { symbol: sym, data: [], error: extractErrorMessage(e, 'داده دریافت نشد') } }
        })
      )
      setDashboardCharts(charts)
    } catch { setDefaultDashboardSymbols([]); setDashboardCharts([]) }
  }, [fetchChart])

  // ── effects ──
  useEffect(() => { Promise.all([loadUsers(), loadDashboard()]).catch(() => null) }, [loadDashboard, loadUsers])
  useEffect(() => {
    if (sourceFilter === 'DBNOMICS') loadDbnomicsProviders().catch(() => null)
    else { setDbnomicsProviderFilter(''); setDbnomicsProviders([]) }
  }, [loadDbnomicsProviders, sourceFilter])
  useEffect(() => { if (selectedUserId) loadUserDashboard(selectedUserId) }, [loadUserDashboard, selectedUserId])
  useEffect(() => {
    if (!_msg?.text) return
    const t = setTimeout(() => _setMsg(null), 5000)
    return () => clearTimeout(t)
  }, [_msg])
  useEffect(() => {
    if (!autoRefreshInterval) return
    const t = setInterval(() => { loadDashboard(); if (selectedUserId) loadUserDashboard(selectedUserId) }, autoRefreshInterval * 60000)
    return () => clearInterval(t)
  }, [autoRefreshInterval, loadDashboard, loadUserDashboard, selectedUserId])

  useEffect(() => {
    if (quickSearchTimer.current) clearTimeout(quickSearchTimer.current)
    if (!quickSearchQuery || quickSearchQuery.length < 2) { setQuickSearchResults([]); return }
    quickSearchTimer.current = setTimeout(async () => {
      setQuickSearchLoading(true)
      try {
        const r = await axios.get(`${API_BASE}/data/symbols/available`, {
          params: { search: quickSearchQuery, limit: 12, page: 1, page_size: 12, paginated: true }
        })
        setQuickSearchResults(r.data?.items || [])
      } catch { setQuickSearchResults([]) }
      finally { setQuickSearchLoading(false) }
    }, 300)
    return () => clearTimeout(quickSearchTimer.current)
  }, [quickSearchQuery, API_BASE])
  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault(); setQuickSearchOpen(v => !v); setQuickSearchQuery(''); return
      }
      if (e.key === 'Escape') {
        if (quickSearchOpen) { setQuickSearchOpen(false); return }
        setExpandedOpen(false); return
      }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return
      if (e.key === 'd') setActiveTab('dashboard')
      if (e.key === 's') setActiveTab('sources')
      if (e.key === 'm') setActiveTab('manage')
      if (e.key === 'l') setActiveTab('lab')
      if (e.key === 'r') loadDashboard()
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [setActiveTab, quickSearchOpen, loadDashboard])

  const debounceRef = useRef(null)
  const handleSearch = useCallback((val) => {
    setSearch(val); setSymbolsPage(1)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => loadDashboard(), 350)
  }, [loadDashboard])

  // ── actions ──
  const persist = useCallback(async (next, okMsg) => {
    if (!selectedUserId) return setMessage('ابتدا وارد حساب کاربری شو.', 'warning')
    try {
      await axios.put(`${API_BASE}/users/${selectedUserId}/dashboard`, { symbols: next })
      setDefaultDashboardSymbols(next)
      await loadUserDashboard(selectedUserId)
      if (okMsg) setMessage(okMsg, 'success')
    } catch (e) { setMessage(extractErrorMessage(e, 'ذخیره ناموفق بود.'), 'error') }
  }, [loadUserDashboard, selectedUserId, setMessage])

  const runPipeline = async (path, okMsg) => {
    try {
      await axios.post(`${API_BASE}${path}`)
      setMessage(okMsg, 'success')
      await loadDashboard()
      if (selectedUserId) await loadUserDashboard(selectedUserId)
    } catch (e) { setMessage(extractErrorMessage(e, 'ارسال دستور ناموفق.'), 'error') }
  }

  const changeInterval = async (sym, days) => {
    if (!days || days < 1) return
    await axios.put(`${API_BASE}/data/symbols/${sym}/interval`, { update_interval_days: Number(days) })
    await loadDashboard()
  }

  const refreshNow = async (sym) => {
    try {
      await axios.post(`${API_BASE}/data/symbols/${sym}/refresh-now`)
      setMessage(`دریافت فوری ${sym} انجام شد.`, 'success')
      await loadDashboard()
      if (selectedUserId) await loadUserDashboard(selectedUserId)
    } catch (e) { setMessage(extractErrorMessage(e, 'رفرش فوری ناموفق.'), 'error') }
  }

  const openExpanded = async (sym, initData = null) => {
    setExpandedSym(sym); setExpandedRange('ALL')
    setExpandedSym2(''); setExpandedData2([])
    setExpandedOpen(true)
    if (initData?.length) { setExpandedData(initData); return }
    try { setExpandedData(await fetchChart(sym)) } catch { setExpandedData([]) }
  }

  const loadCompare = async (sym) => {
    setExpandedSym2(sym)
    if (!sym) { setExpandedData2([]); return }
    try { setExpandedData2(await fetchChart(sym)) } catch { setExpandedData2([]) }
  }

  const addUser = async () => {
    try {
      const r = await axios.post(`${API_BASE}/users`, { username: newUsername, display_name: newDisplayName })
      setNewUsername(''); setNewDisplayName('')
      await loadUsers()
      const id = String(r.data?.id || '')
      if (id) setLoginUserId(id)
      setMessage('کاربر جدید ساخته شد.', 'success')
    } catch (e) { setMessage(extractErrorMessage(e, 'ساخت کاربر ناموفق.'), 'error') }
  }

  const login = async () => {
    if (!loginUserId) return setMessage('یک کاربر انتخاب کن.', 'warning')
    setSelectedUserId(loginUserId)
    localStorage.setItem(ACTIVE_USER_STORAGE_KEY, String(loginUserId))
    setActiveTab('dashboard')
    await loadUserDashboard(loginUserId)
    setMessage('ورود با موفقیت انجام شد.', 'success')
  }

  const logout = () => {
    setSelectedUserId(''); setDefaultDashboardSymbols([]); setDashboardCharts([])
    localStorage.removeItem(ACTIVE_USER_STORAGE_KEY)
    setMessage('خروج انجام شد.', 'info')
  }

  const addToDashboard = async (sym) => {
    if (defaultDashboardSymbols.includes(sym)) return
    if (defaultDashboardSymbols.length >= MAX_DASHBOARD_SYMBOLS)
      return setMessage(`حداکثر ${MAX_DASHBOARD_SYMBOLS} نماد مجاز است.`, 'warning')
    await persist([...defaultDashboardSymbols, sym], `${sym} به داشبورد اضافه شد.`)
  }

  const addSelectedToDashboard = async () => {
    if (!selectedSymbols.length) return setMessage('ابتدا نمادهایی انتخاب کن.', 'warning')
    const next = [...new Set([...defaultDashboardSymbols, ...selectedSymbols])]
    if (next.length > MAX_DASHBOARD_SYMBOLS)
      return setMessage(`مجموع نمی‌تواند بیشتر از ${MAX_DASHBOARD_SYMBOLS} باشد.`, 'warning')
    await persist(next, `${selectedSymbols.length} نماد اضافه شد.`)
  }

  const refreshVisible = async () => {
    const list = selectedSymbols.length > 0
      ? selectedSymbols
      : symbols.filter(s => sourceSupportsRefresh(s.source)).slice(0, 30).map(s => s.symbol)
    if (!list.length) return setMessage('نماد قابل رفرش پیدا نشد.', 'warning')
    try {
      const r = await axios.post(`${API_BASE}/data/symbols/bulk-refresh`, { symbols: list })
      setMessage(r.data?.message || `رفرش ${list.length} شاخص آغاز شد.`, 'success')
    } catch (e) {
      setMessage(extractErrorMessage(e, 'رفرش گروهی ناموفق.'), 'error')
    }
  }

  const removeFromDashboard = async (sym) =>
    persist(defaultDashboardSymbols.filter(s => s !== sym), `${sym} از داشبورد حذف شد.`)

  // ── memos ──
  const availableSources = useMemo(() => (summary?.sources || []).map(s => s.source), [summary])

  const expandedFiltered = useMemo(() => filterByRange(expandedData, expandedRange), [expandedData, expandedRange])
  const expandedStats = useMemo(() => {
    const vs = expandedFiltered.map(d => Number(d.value)).filter(Number.isFinite)
    if (!vs.length) return { avg: null, min: null, max: null }
    return {
      avg: vs.reduce((a, b) => a + b, 0) / vs.length,
      min: Math.min(...vs),
      max: Math.max(...vs),
    }
  }, [expandedFiltered])
  const expandedAvg = expandedStats.avg

  const mergedData = useMemo(() => {
    if (!expandedData2.length || !expandedSym2) return null
    const map2 = Object.fromEntries(filterByRange(expandedData2, expandedRange).map(d => [d.date, d.value]))
    return expandedFiltered.map(d => ({ ...d, value2: map2[d.date] ?? null }))
  }, [expandedData2, expandedSym2, expandedRange, expandedFiltered])

  const symbolMap = useMemo(() =>
    Object.fromEntries(symbols.map(s => [s.symbol, s])), [symbols])

  const freshnessMap = useMemo(() =>
    Object.fromEntries((freshness?.items || []).map(i => [i.symbol, i])), [freshness])

  // ── login guard ──
  if (!isLoggedIn) {
    return <LoginView {...{ users, loginUserId, setLoginUserId, login, newUsername, setNewUsername, newDisplayName, setNewDisplayName, addUser, backendOk, msg: _msg }} />
  }

  const initials = (activeUser?.display_name || '?')
    .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100" dir="rtl">
      <div className="max-w-7xl mx-auto px-4 py-5 space-y-5">

        {/* ── Header ── */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 shrink-0">
              <Activity size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-l from-cyan-300 to-blue-400 bg-clip-text text-transparent">
                پنل اقتصاد جهانی
              </h1>
              <div className="flex items-center gap-2 text-xs">
                <span className={`w-1.5 h-1.5 rounded-full ${backendOk === false ? 'bg-rose-500' : 'bg-emerald-400'}`} />
                <span className="text-slate-400">{activeUser?.display_name}</span>
                {(freshness?.totals?.stale ?? 0) > 0 && (
                  <span className="bg-rose-700/60 text-rose-300 px-1.5 py-0.5 rounded-full text-[10px]">
                    {freshness.totals.stale} دیرهنگام
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex gap-1.5 flex-wrap items-center">
            <button onClick={() => { setQuickSearchOpen(true); setQuickSearchQuery('') }}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs flex items-center gap-1.5 transition-colors">
              <Search size={12} /> <span className="hidden sm:inline">جستجو</span>
              <kbd className="text-[10px] text-slate-500 bg-slate-700 px-1 rounded">⌘K</kbd>
            </button>
            <button onClick={loadDashboard}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs flex items-center gap-1.5 transition-colors">
              <RefreshCcw size={12} className={loading ? 'animate-spin' : ''} /> رفرش
            </button>
            <select value={autoRefreshInterval} onChange={e => setAutoRefreshInterval(Number(e.target.value))}
              title="رفرش خودکار"
              className="bg-slate-800 hover:bg-slate-700 border-0 rounded-lg px-3 py-1.5 text-xs transition-colors cursor-pointer">
              <option value={0}>خودکار: خاموش</option>
              <option value={1}>هر ۱ دقیقه</option>
              <option value={5}>هر ۵ دقیقه</option>
              <option value={15}>هر ۱۵ دقیقه</option>
              <option value={60}>هر ۱ ساعت</option>
            </select>
            <button onClick={() => runPipeline('/discover/auto-spider?source=ALL', 'کاوش همه ۱۴ منبع آغاز شد.')}
              className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-xs font-medium transition-colors">
              🌍 کاوش همه
            </button>
            <button onClick={() => runPipeline('/pipeline/trigger-all', 'دریافت موازی ۲۴ شاخص مهم شروع شد.')}
              title="دریافت موازی GDP، CPI، نرخ بهره، طلا، نفت، ارز، سهام و کریپتو"
              className="px-3 py-1.5 bg-cyan-700 hover:bg-cyan-600 rounded-lg text-xs transition-colors">
              ⚡ دریافت سریع
            </button>
            <button onClick={() => runPipeline('/discover/dbnomics', 'کاوش بانک‌های مرکزی آغاز شد.')}
              className="px-3 py-1.5 bg-fuchsia-700 hover:bg-fuchsia-600 rounded-lg text-xs transition-colors">
              🏦 DBNOMICS
            </button>
            <div className="relative">
              <button onClick={() => setNotifOpen(v => !v)}
                className="relative w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center transition-colors"
                title="اعلانات">
                <Bell size={14} className="text-slate-400" />
                {(freshness?.totals?.stale ?? 0) > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-rose-600 rounded-full text-[9px] flex items-center justify-center font-bold">
                    {Math.min(freshness.totals.stale, 99)}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute left-0 top-10 w-72 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-40 overflow-hidden">
                  <div className="px-3 py-2 border-b border-slate-800 text-xs font-semibold text-slate-400">اعلانات</div>
                  <div className="max-h-64 overflow-y-auto">
                    {freshness?.items?.filter(i => i.status === 'stale' || i.status === 'never_updated')
                      .sort((a, b) => (b.days_since_update ?? 9999) - (a.days_since_update ?? 9999))
                      .slice(0, 10)
                      .map(item => (
                        <button key={item.symbol} onClick={() => { openExpanded(item.symbol); setNotifOpen(false) }}
                          className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-800 transition-colors text-right">
                          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${item.status === 'stale' ? 'bg-rose-400' : 'bg-purple-400'}`} />
                          <span className="font-mono text-xs text-cyan-300">{item.symbol}</span>
                          <span className="text-[10px] text-slate-500 mr-auto shrink-0">
                            {item.days_since_update != null ? `${item.days_since_update}ر` : 'هرگز'}
                          </span>
                        </button>
                      ))}
                    {(freshness?.totals?.stale ?? 0) === 0 && (freshness?.totals?.never_updated ?? 0) === 0 && (
                      <div className="py-6 text-center text-xs text-slate-600">همه شاخص‌ها به‌روز هستند ✓</div>
                    )}
                    {!freshness && (
                      <div className="py-6 text-center text-xs text-slate-600">در حال بارگذاری...</div>
                    )}
                  </div>
                </div>
              )}
            </div>
            <button title="خروج" onClick={logout}
              className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-rose-800/60 flex items-center justify-center text-xs font-bold transition-colors">
              {initials}
            </button>
          </div>
        </header>

        {/* ── Toast ── */}
        {_msg?.text && <Toast msg={_msg} onDismiss={() => _setMsg(null)} />}

        {/* ── Tabs ── */}
        <nav className="flex items-center gap-2">
        <div className="flex gap-1 bg-slate-900/60 rounded-xl p-1 overflow-x-auto">
          {[
            ['dashboard', 'داشبورد', null],
            ['sources', 'منابع', summary?.sources?.length],
            ['manage', 'مدیریت', symbolsTotal || null],
            ['users', 'حساب', null],
            ['lab', 'آزمایشگاه', null],
          ].map(([k, l, badge]) => (
            <button key={k} onClick={() => setActiveTab(k)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap flex items-center gap-1.5 ${activeTab === k ? 'bg-cyan-700 text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'}`}>
              {l}
              {badge != null && (
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${activeTab === k ? 'bg-cyan-600' : 'bg-slate-700 text-slate-500'}`}>
                  {badge > 9999 ? `${Math.round(badge/1000)}k` : badge}
                </span>
              )}
            </button>
          ))}
        </div>
        <span title="میانبر صفحه‌کلید: D داشبورد، S منابع، M مدیریت، L آزمایشگاه، R رفرش، ESC بستن پنجره، Ctrl+K جستجو"
          className="text-slate-700 hover:text-slate-500 cursor-help text-xs hidden sm:block select-none">⌨</span>
        </nav>

        {/* ── Dashboard ── */}
        {activeTab === 'dashboard' && (
          <section className="space-y-5">
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              <StatCard title="کل شاخص‌ها" value={summary?.totals?.indicators} Icon={Database} color="#38bdf8"
                sub={`از ${summary?.sources?.length ?? 0} منبع`} />
              <StatCard title="دارای داده" value={summary?.totals?.indicators_with_data} Icon={CheckCircle} color="#34d399"
                sub={summary?.totals?.indicators > 0 ? `${Math.round((summary.totals.indicators_with_data / summary.totals.indicators) * 100)}% پوشش` : undefined} />
              <StatCard title="کل رکوردها" value={summary?.totals?.economic_data_points} Icon={Activity} color="#a78bfa"
                sub="نقطه داده اقتصادی" />
              <StatCard title="دیرهنگام" value={freshness?.totals?.stale} Icon={Clock} color="#fb923c"
                sub={freshness?.totals?.all > 0 ? `${Math.round((freshness.totals.stale / freshness.totals.all) * 100)}% از کل` : undefined} />
              <StatCard title="بدون آپدیت" value={freshness?.totals?.never_updated} Icon={AlertTriangle} color="#f472b6"
                sub={freshness?.totals?.all > 0 ? `${Math.round((freshness.totals.never_updated / freshness.totals.all) * 100)}% از کل` : undefined} />
            </div>

            {/* Source bar */}
            {summary?.sources?.length > 0 && (
              <div className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-xs text-slate-500">توزیع شاخص‌ها بر اساس منبع</div>
                  <div className="text-[10px] text-slate-600">کلیک برای فیلتر مدیریت</div>
                </div>
                <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5">
                  {summary.sources.map(s => {
                    const color = SOURCE_COLOR_MAP[s.source] || '#64748b'
                    const pct = summary.totals.indicators > 0
                      ? Math.round((s.indicators / summary.totals.indicators) * 100) : 0
                    const dataPct = s.indicators > 0
                      ? Math.round((s.indicators_with_data / s.indicators) * 100) : 0
                    return (
                      <button key={s.source} onClick={() => { setSourceFilter(s.source); setActiveTab('manage') }}
                        className="flex items-center gap-2 text-xs hover:bg-slate-800/50 rounded-lg px-1 py-0.5 transition-colors w-full text-right">
                        <span className="w-20 shrink-0 font-mono" style={{ color }}>{s.source}</span>
                        <div className="flex-1 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                        </div>
                        <span className="w-16 text-right text-slate-500">{s.indicators_with_data}/{s.indicators}</span>
                        <span className="w-10 text-right" style={{ color: dataPct > 50 ? color : '#64748b' }}>{dataPct}%</span>
                        {s.data_points > 0 && (
                          <span className="text-[10px] text-slate-700 shrink-0 hidden lg:block w-16">{fmt(s.data_points)}</span>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* My charts */}
            <div className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold flex items-center gap-2 text-sm"><Users size={14} /> داشبورد شخصی</h3>
                <span className="text-xs text-slate-500">{defaultDashboardSymbols.length}/{MAX_DASHBOARD_SYMBOLS}</span>
              </div>
              {dashboardCharts.length === 0 ? (
                <div className="py-10 text-center text-slate-600 space-y-3">
                  <Database size={32} className="mx-auto opacity-20" />
                  <p className="text-sm">شاخصی به داشبورد اضافه نشده</p>
                  {(summary?.totals?.indicators ?? 0) === 0 ? (
                    <div className="max-w-sm mx-auto bg-slate-950 border border-slate-800 rounded-xl p-4 text-right space-y-2">
                      <p className="text-xs text-slate-500 font-semibold">شروع سریع:</p>
                      <ol className="text-xs text-slate-500 list-decimal list-inside space-y-1">
                        <li>روی <strong className="text-cyan-500">⚡ دریافت سریع</strong> کلیک کن تا ۲۴ شاخص مهم جهانی دانلود شود</li>
                        <li>یا روی <strong className="text-emerald-500">🌍 کاوش همه</strong> کلیک کن تا همه ۱۴ منبع کاوش شوند</li>
                        <li>از تب <strong className="text-indigo-400">مدیریت</strong>، شاخص‌ها را جستجو و به داشبورد اضافه کن</li>
                      </ol>
                    </div>
                  ) : (
                    <p className="text-xs">از تب <strong className="text-indigo-400">مدیریت</strong>، شاخص‌ها را انتخاب و اضافه کن</p>
                  )}
                </div>
              ) : (
                <div className="grid lg:grid-cols-2 gap-4">
                  {dashboardCharts.map(chart => {
                    const rangeKey = dashboardRanges[chart.symbol] || 'ALL'
                    const inRange = filterByRange(chart.data, rangeKey)
                    const last = inRange.length ? inRange[inRange.length - 1].value : null
                    const delta = getDelta(inRange)
                    const symInfo = symbolMap[chart.symbol]
                    const src = symInfo?.source || ''
                    const indName = symInfo?.name || ''
                    const lastUpdated = symInfo?.last_updated
                    const daysSince = lastUpdated
                      ? Math.floor((Date.now() - new Date(lastUpdated).getTime()) / 86400000) : null
                    const fsStatus = freshnessMap[chart.symbol]?.status
                    return (
                      <div key={chart.symbol} className="bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-xl p-3 transition-colors">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="font-mono font-semibold text-sm shrink-0">{chart.symbol}</span>
                            {src && <SourceBadge source={src} />}
                          </div>
                          <div className="flex items-center gap-1.5 text-xs">
                            {last !== null ? (
                              <>
                                <span className="text-cyan-300">{fmtFull(last)}</span>
                                {delta != null && (
                                  <span className={`flex items-center gap-0.5 ${delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {delta >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                                    {Math.abs(delta).toFixed(1)}%
                                  </span>
                                )}
                              </>
                            ) : <span className="text-rose-400">{chart.error || 'بدون داده'}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 mb-1.5">
                          {indName && (
                            <span className="text-[10px] text-slate-600 truncate flex-1" title={indName}>{indName}</span>
                          )}
                          {daysSince != null && (
                            <span className={`text-[10px] shrink-0 ${fsStatus === 'stale' ? 'text-rose-500' : fsStatus === 'due_soon' ? 'text-amber-500' : 'text-slate-700'}`}>
                              {daysSince === 0 ? 'امروز' : `${daysSince}ر پیش`}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1 mb-2 flex-wrap">
                          {CHART_RANGES.map(r => (
                            <button key={r.key}
                              onClick={() => setDashboardRanges(p => ({ ...p, [chart.symbol]: r.key }))}
                              className={`px-2 py-0.5 rounded text-[11px] transition-colors ${rangeKey === r.key ? 'bg-cyan-700' : 'bg-slate-800 hover:bg-slate-700'}`}>
                              {r.label}
                            </button>
                          ))}
                          <button onClick={() => openExpanded(chart.symbol, chart.data)}
                            className="px-2 py-0.5 bg-indigo-700 hover:bg-indigo-600 rounded text-[11px] ml-auto transition-colors">
                            <Maximize2 size={11} />
                          </button>
                          <button onClick={() => removeFromDashboard(chart.symbol)}
                            className="px-2 py-0.5 bg-rose-800 hover:bg-rose-700 rounded text-[11px] transition-colors">×</button>
                        </div>
                        <div className="h-[190px]">
                          {(() => {
                            const clr = SOURCE_COLOR_MAP[src] || '#38bdf8'
                            return (
                              <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={inRange}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                  <XAxis dataKey="date" hide stroke="#475569" />
                                  <YAxis stroke="#475569" width={44} tickFormatter={fmt} tick={{ fontSize: 10 }} />
                                  <Tooltip formatter={fmtFull} contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
                                  <Area dataKey="value" stroke={clr} fill={`${clr}18`} strokeWidth={1.5} dot={false} />
                                </AreaChart>
                              </ResponsiveContainer>
                            )
                          })()}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Recent Activity */}
            {recentActivity.length > 0 && (
              <div className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4">
                <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
                  <Clock size={14} className="text-cyan-400" /> آخرین آپدیت‌ها
                </h3>
                <div className="grid sm:grid-cols-2 gap-1.5">
                  {recentActivity.map(item => (
                    <button key={item.symbol} onClick={() => openExpanded(item.symbol)}
                      className="flex items-center justify-between bg-slate-950 hover:bg-slate-900 rounded-lg px-3 py-2 text-xs transition-colors text-right">
                      <div className="flex items-center gap-2 min-w-0">
                        <SourceBadge source={item.source} />
                        <span className="font-mono text-cyan-300">{item.symbol}</span>
                        <span className="text-slate-500 truncate hidden sm:block">{item.name?.slice(0, 25)}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {item.data_points_count > 0 && (
                          <span className="text-emerald-500">{fmt(item.data_points_count)}</span>
                        )}
                        <span className="text-slate-600">{item.last_updated}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Top series by data volume */}
            {topSeries.length > 0 && (
              <div className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4">
                <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
                  <TrendingUp size={14} className="text-emerald-400" /> پُرداده‌ترین شاخص‌ها
                </h3>
                <div className="space-y-1.5">
                  {topSeries.map((item, i) => {
                    const max = topSeries[0]?.data_points_count || 1
                    const pct = Math.round((item.data_points_count / max) * 100)
                    const color = SOURCE_COLOR_MAP[item.source] || '#64748b'
                    return (
                      <button key={item.symbol} onClick={() => openExpanded(item.symbol)}
                        className="w-full flex items-center gap-3 text-xs hover:bg-slate-800/50 rounded-lg px-2 py-1.5 transition-colors">
                        <span className="text-slate-600 w-4 shrink-0">{i + 1}</span>
                        <SourceBadge source={item.source} />
                        <span className="font-mono text-cyan-300 shrink-0 w-28 truncate text-right">{item.symbol}</span>
                        <div className="flex-1 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                        </div>
                        <span className="text-emerald-400 shrink-0 w-16 text-left">{fmt(item.data_points_count)}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Freshness */}
            {freshness?.totals && (
              <div className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4">
                <h3 className="font-semibold text-sm flex items-center gap-2 mb-3"><WandSparkles size={14} /> سلامت فید جهانی</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                  {[
                    { k: 'healthy',       l: 'سالم',          c: '#34d399' },
                    { k: 'due_soon',      l: 'نزدیک سررسید',  c: '#fb923c' },
                    { k: 'stale',         l: 'دیرهنگام',      c: '#f43f5e' },
                    { k: 'never_updated', l: 'بدون آپدیت',    c: '#a78bfa' },
                  ].map(({ k, l, c }) => {
                    const val = freshness.totals[k] ?? 0
                    const tot = freshness.totals.all || 1
                    const pct = Math.round((val / tot) * 100)
                    return (
                      <div key={k} className="bg-slate-950 rounded-xl p-3">
                        <div className="flex justify-between mb-1">
                          <span className="text-xs text-slate-400">{l}</span>
                          <span className="text-sm font-bold" style={{ color: c }}>{val}</span>
                        </div>
                        <div className="bg-slate-800 rounded-full h-1.5">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: c }} />
                        </div>
                        <div className="text-[10px] text-slate-600 mt-1">{pct}%</div>
                      </div>
                    )
                  })}
                </div>
                {/* Top stale indicators */}
                {freshness?.items?.filter(i => i.status === 'stale').length > 0 && (
                  <div>
                    <div className="text-[11px] text-slate-600 mb-2">دیرهنگام‌ترین شاخص‌ها:</div>
                    <div className="grid sm:grid-cols-2 gap-1.5">
                      {freshness.items
                        .filter(i => i.status === 'stale')
                        .sort((a, b) => (b.days_since_update ?? 0) - (a.days_since_update ?? 0))
                        .slice(0, 8)
                        .map(item => (
                          <div key={item.id}
                            className="flex items-center justify-between bg-slate-950 rounded-lg px-3 py-1.5 text-[11px]">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <SourceBadge source={item.source} />
                              <span className="font-mono truncate">{item.symbol}</span>
                            </div>
                            <span className="text-rose-400 shrink-0">{item.days_since_update}روز پیش</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {activeTab === 'sources' && (
          <SourcesPanel summary={summary} freshness={freshness} runPipeline={runPipeline} setMessage={setMessage} />
        )}

        {/* ── Manage ── */}
        {activeTab === 'manage' && (
          <section className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4 space-y-4">
            {/* Filters */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-10 gap-2">
              <label className="col-span-2 bg-slate-950 border border-slate-800 focus-within:border-cyan-700 rounded-lg px-3 py-2 flex items-center gap-2 transition-colors">
                <Search size={13} className="text-slate-500 shrink-0" />
                <input value={search} onChange={e => handleSearch(e.target.value)} placeholder="جستجو..."
                  className="bg-transparent w-full outline-none text-sm" />
              </label>
              <select value={sourceFilter} onChange={e => { setSourceFilter(e.target.value); setSymbolsPage(1) }}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm">
                <option value="">همه منابع</option>
                {availableSources.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <input value={dbnomicsProviderSearch} onChange={e => setDbnomicsProviderSearch(e.target.value)}
                placeholder="جستجو زیرمنبع" disabled={sourceFilter !== 'DBNOMICS'}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm disabled:opacity-40" />
              <select value={dbnomicsProviderFilter} onChange={e => { setDbnomicsProviderFilter(e.target.value); setSymbolsPage(1) }}
                disabled={sourceFilter !== 'DBNOMICS'} className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm disabled:opacity-40">
                <option value="">زیرمنبع</option>
                {dbnomicsProviders.map(p => <option key={p.provider} value={p.provider}>{p.provider} ({p.indicators})</option>)}
              </select>
              <select value={sortBy} onChange={e => { setSortBy(e.target.value); setSymbolsPage(1) }}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm">
                <option value="source">منبع</option><option value="name">نام</option>
                <option value="symbol">نماد</option><option value="updated">آپدیت</option>
                <option value="points">رکورد</option>
              </select>
              <select value={sortDir} onChange={e => { setSortDir(e.target.value); setSymbolsPage(1) }}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm">
                <option value="asc">صعودی</option><option value="desc">نزولی</option>
              </select>
              <label className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={withDataOnly} onChange={e => { setWithDataOnly(e.target.checked); setSymbolsPage(1) }} />
                <SlidersHorizontal size={12} className="text-slate-500" /> دارای دیتا
              </label>
              <input value={tagFilter} onChange={e => setTagFilter(e.target.value)}
                placeholder="فیلتر تگ..."
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm" />
              <select value={symbolsPageSize} onChange={e => { setSymbolsPageSize(Number(e.target.value)); setSymbolsPage(1) }}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm">
                <option value={50}>۵۰</option><option value={100}>۱۰۰</option>
                <option value={200}>۲۰۰</option><option value={500}>۵۰۰</option>
              </select>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button onClick={addSelectedToDashboard}
                className="px-3 py-1.5 bg-indigo-700 hover:bg-indigo-600 rounded-lg text-xs transition-colors">
                افزودن انتخاب‌شده ({selectedSymbols.length})
              </button>
              <button onClick={refreshVisible}
                title={selectedSymbols.length > 0 ? `رفرش ${selectedSymbols.length} نماد انتخاب‌شده` : 'رفرش ۳۰ نماد اول صفحه در پس‌زمینه'}
                className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 rounded-lg text-xs transition-colors">
                {selectedSymbols.length > 0 ? `رفرش انتخاب‌شده (${selectedSymbols.length})` : 'رفرش گروهی'}
              </button>
              <button onClick={() => setSelectedSymbols([])}
                className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs transition-colors">
                پاک انتخاب
              </button>
              <button onClick={() => {
                if (!symbols.length) return
                const rows = symbols.map(s => `${s.symbol},${s.source},"${(s.name||'').replace(/"/g, '')}",${s.data_points_count ?? 0},${s.last_updated ?? ''}`)
                const csv = ['symbol,source,name,data_points,last_updated', ...rows].join('\n')
                const a = Object.assign(document.createElement('a'), {
                  href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
                  download: `indicators_${new Date().toISOString().slice(0, 10)}.csv`,
                })
                a.click(); URL.revokeObjectURL(a.href)
              }}
                className="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 rounded-lg text-xs flex items-center gap-1 transition-colors">
                <Download size={11} /> خروجی CSV
              </button>
              <button onClick={loadDashboard}
                className="px-3 py-1.5 bg-cyan-700 hover:bg-cyan-600 rounded-lg text-xs mr-auto transition-colors">
                اعمال فیلتر
              </button>
            </div>

            <div className="overflow-auto max-h-[560px] rounded-xl border border-slate-800">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-900 text-slate-500 text-xs">
                  <tr>
                    <th className="p-2.5 text-right w-8">
                      <input type="checkbox"
                        onChange={e => setSelectedSymbols(e.target.checked ? symbols.map(s => s.symbol) : [])}
                        checked={symbols.length > 0 && selectedSymbols.length === symbols.length} />
                    </th>
                    <th className="p-2.5 text-right">نماد</th>
                    <th className="p-2.5 text-right">نام</th>
                    <th className="p-2.5 text-right">منبع</th>
                    <th className="p-2.5 text-right">رکورد</th>
                    <th className="p-2.5 text-right hidden md:table-cell">آپدیت</th>
                    <th className="p-2.5 text-right">بازه (روز)</th>
                    <th className="p-2.5 text-right">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {[...symbols]
                    .filter(row => !tagFilter || (row.tags || '').toLowerCase().includes(tagFilter.toLowerCase()))
                    .sort((a, b) => {
                    const pa = pinnedSymbols.includes(a.symbol) ? 0 : 1
                    const pb = pinnedSymbols.includes(b.symbol) ? 0 : 1
                    return pa - pb
                  }).map(row => (
                    <tr key={row.id}
                      className={`border-t border-slate-800/60 hover:bg-slate-800/20 transition-colors ${selectedSymbols.includes(row.symbol) ? 'bg-cyan-900/10' : ''} ${pinnedSymbols.includes(row.symbol) ? 'bg-amber-900/5' : ''}`}>
                      <td className="p-2.5">
                        <input type="checkbox" checked={selectedSymbols.includes(row.symbol)}
                          onChange={e => setSelectedSymbols(p => e.target.checked
                            ? [...new Set([...p, row.symbol])]
                            : p.filter(s => s !== row.symbol))} />
                      </td>
                      <td className="p-2.5 font-mono text-xs">
                        <div className="flex items-center gap-1.5">
                          <button onClick={() => togglePin(row.symbol)}
                            title={pinnedSymbols.includes(row.symbol) ? 'از پین خارج کن' : 'پین کن'}
                            className={`text-[10px] shrink-0 transition-colors ${pinnedSymbols.includes(row.symbol) ? 'text-amber-400' : 'text-slate-700 hover:text-slate-500'}`}>
                            📌
                          </button>
                          {(() => {
                            const fst = freshnessMap[row.symbol]?.status
                            const c = { healthy: '#34d399', due_soon: '#fb923c', stale: '#f43f5e', never_updated: '#a78bfa' }[fst]
                            return c ? <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c }} title={fst} /> : null
                          })()}
                          {row.symbol}
                        </div>
                      </td>
                      <td className="p-2.5 text-slate-300 max-w-[180px] text-xs">
                        <div className="truncate" title={row.name}>{row.name}</div>
                        {row.tags && (
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {row.tags.split(',').map(t => t.trim()).filter(Boolean).map(t => (
                              <span key={t} className="bg-indigo-900/40 text-indigo-300 px-1.5 py-0 rounded text-[10px]">#{t}</span>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="p-2.5"><SourceBadge source={row.source} /></td>
                      <td className="p-2.5 text-xs">
                        {row.data_points_count > 0
                          ? <span className="text-emerald-400">{fmt(row.data_points_count)}</span>
                          : <span className="text-slate-700">—</span>}
                      </td>
                      <td className="p-2.5 text-[11px] text-slate-500 hidden md:table-cell">
                        {row.last_updated
                          ? <span title={row.last_updated}>{row.last_updated}</span>
                          : <span className="text-slate-700">—</span>}
                      </td>
                      <td className="p-2.5">
                        <div className="flex items-center gap-1">
                          <input defaultValue={row.update_interval_days} type="number" min="1"
                            className="w-14 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-xs"
                            onBlur={e => changeInterval(row.symbol, e.target.value)} />
                          <span className="text-slate-600 text-[10px]">روز</span>
                        </div>
                      </td>
                      <td className="p-2.5">
                        <div className="flex gap-1">
                          <button onClick={() => openExpanded(row.symbol)}
                            className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded text-xs transition-colors">
                            نمایش
                          </button>
                          <button disabled={!sourceSupportsRefresh(row.source)}
                            onClick={() => refreshNow(row.symbol)}
                            className="px-2 py-1 bg-emerald-700 hover:bg-emerald-600 disabled:bg-slate-700 disabled:opacity-40 rounded text-xs transition-colors">
                            دریافت
                          </button>
                          <button onClick={() => addToDashboard(row.symbol)}
                            className="px-2 py-1 bg-indigo-700 hover:bg-indigo-600 rounded text-xs transition-colors">+</button>
                          <button onClick={async () => {
                            const current = row.tags || ''
                            const input = prompt(`تگ‌های ${row.symbol} (با کاما جدا کنید):`, current)
                            if (input === null) return
                            try {
                              await axios.patch(`${API_BASE}/data/symbols/${row.symbol}/tags`, { tags: input || null })
                              await loadDashboard()
                            } catch (e) { setMessage(extractErrorMessage(e, 'خطا در ذخیره تگ'), 'error') }
                          }}
                            title="ویرایش تگ‌ها"
                            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs transition-colors">🏷</button>
                          <button onClick={async () => {
                            if (!confirm(`آیا مطمئنی که می‌خواهی ${row.symbol} را حذف کنی؟`)) return
                            try {
                              await axios.delete(`${API_BASE}/data/symbols/${row.symbol}`)
                              setMessage(`${row.symbol} حذف شد.`, 'success')
                              await loadDashboard()
                            } catch (e) { setMessage(extractErrorMessage(e, 'حذف ناموفق.'), 'error') }
                          }}
                            className="px-2 py-1 bg-slate-700 hover:bg-rose-700 rounded text-xs transition-colors text-slate-400 hover:text-white">
                            ✕
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!loading && symbols.length === 0 && (
                <div className="text-center py-10 text-slate-600 text-sm">
                  <Search size={28} className="mx-auto mb-2 opacity-20" /> نتیجه‌ای پیدا نشد
                </div>
              )}
              {loading && <div className="text-center py-10 text-slate-600 text-sm animate-pulse">در حال بارگذاری...</div>}
            </div>

            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">نمایش {symbols.length} از {symbolsTotal}</span>
                {pinnedSymbols.length > 0 && (
                  <span className="text-[10px] bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded-full">
                    {pinnedSymbols.length} پین‌شده
                  </span>
                )}
                {tagFilter && (
                  <button onClick={() => setTagFilter('')}
                    className="text-[10px] bg-indigo-900/30 text-indigo-300 px-2 py-0.5 rounded-full flex items-center gap-1 hover:bg-indigo-900/50 transition-colors">
                    #{tagFilter} ✕
                  </button>
                )}
              </div>
              <div className="flex items-center gap-1">
                <button disabled={symbolsPage <= 1} onClick={() => setSymbolsPage(1)}
                  className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs disabled:opacity-40 transition-colors">⟪</button>
                <button disabled={symbolsPage <= 1} onClick={() => setSymbolsPage(p => p - 1)}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs disabled:opacity-40 transition-colors">«</button>
                <span className="px-3 py-1 bg-slate-900 rounded-lg text-xs">{symbolsPage} / {symbolsTotalPages}</span>
                <button disabled={symbolsPage >= symbolsTotalPages} onClick={() => setSymbolsPage(p => p + 1)}
                  className="px-3 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs disabled:opacity-40 transition-colors">»</button>
                <button disabled={symbolsPage >= symbolsTotalPages} onClick={() => setSymbolsPage(symbolsTotalPages)}
                  className="px-2 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs disabled:opacity-40 transition-colors">⟫</button>
              </div>
            </div>
          </section>
        )}

        {/* ── Users ── */}
        {activeTab === 'users' && (
          <section className="grid lg:grid-cols-2 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
              <h3 className="font-semibold flex items-center gap-2"><UserPlus size={15} /> افزودن کاربر جدید</h3>
              <input value={newUsername} onChange={e => setNewUsername(e.target.value)} placeholder="username"
                className="w-full bg-slate-950 border border-slate-800 focus:border-cyan-700 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors" />
              <input value={newDisplayName} onChange={e => setNewDisplayName(e.target.value)} placeholder="نام نمایشی"
                onKeyDown={e => e.key === 'Enter' && addUser()}
                className="w-full bg-slate-950 border border-slate-800 focus:border-cyan-700 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors" />
              <button onClick={addUser}
                className="w-full bg-cyan-700 hover:bg-cyan-600 rounded-xl py-2.5 text-sm font-medium transition-colors">
                ساخت کاربر
              </button>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
              <h3 className="font-semibold flex items-center gap-2"><Users size={15} /> داشبورد اختصاصی</h3>
              <div className="text-xs text-slate-500">{defaultDashboardSymbols.length} از {MAX_DASHBOARD_SYMBOLS} نماد</div>
              <div className="flex gap-2 flex-wrap">
                {defaultDashboardSymbols.length === 0
                  ? <span className="text-xs text-slate-700">هنوز نمادی اضافه نشده</span>
                  : defaultDashboardSymbols.map(s => (
                    <button key={s} onClick={() => removeFromDashboard(s)}
                      className="px-2 py-1 bg-slate-800 hover:bg-rose-900/40 rounded-lg text-xs flex items-center gap-1 transition-colors">
                      <span className="font-mono">{s}</span>
                      <span className="text-slate-500 text-xs">×</span>
                    </button>
                  ))}
              </div>
            </div>
          </section>
        )}

        {activeTab === 'lab' && (
          <LabPanel symbols={symbols} API_BASE={API_BASE} setMessage={setMessage} />
        )}
      </div>

      {/* ── Expanded Chart Modal ── */}
      {expandedOpen && (
        <div className="fixed inset-0 bg-slate-950/95 z-50 flex flex-col p-3 md:p-5" dir="rtl">
          <div className="max-w-7xl w-full mx-auto flex-1 flex flex-col bg-slate-900 border border-slate-700 rounded-2xl overflow-hidden min-h-0">
            {/* header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800 flex-wrap">
              <span className="font-mono font-bold text-cyan-300">{expandedSym}</span>
              <SourceBadge source={symbolMap[expandedSym]?.source || ''} />

              {/* compare */}
              <div className="flex items-center gap-1.5 bg-slate-950 rounded-lg px-2 py-1 mr-2">
                <span className="text-[11px] text-slate-500">مقایسه:</span>
                <select value={expandedSym2} onChange={e => loadCompare(e.target.value)}
                  className="bg-transparent text-xs outline-none text-slate-300 max-w-[140px]">
                  <option value="">—</option>
                  {symbols.filter(s => s.has_data && s.symbol !== expandedSym).slice(0, 300).map(s => (
                    <option key={s.id} value={s.symbol}>{s.symbol}</option>
                  ))}
                </select>
              </div>

              <div className="mr-auto flex items-center gap-1 flex-wrap">
                {CHART_RANGES.map(r => (
                  <button key={r.key} onClick={() => setExpandedRange(r.key)}
                    className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${expandedRange === r.key ? 'bg-cyan-700' : 'bg-slate-800 hover:bg-slate-700'}`}>
                    {r.label}
                  </button>
                ))}
                <button onClick={() => exportCSV(expandedFiltered, expandedSym)}
                  className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs flex items-center gap-1 transition-colors">
                  <Download size={11} /> CSV (فیلتر)
                </button>
                <a href={`${API_BASE}/data/${expandedSym}/export.csv`} download={`${expandedSym}.csv`}
                  className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 rounded-lg text-xs flex items-center gap-1 transition-colors">
                  <Download size={11} /> CSV (کامل)
                </a>
                {sourceSupportsRefresh(symbolMap[expandedSym]?.source) && (
                  <button onClick={() => refreshNow(expandedSym)}
                    className="px-2.5 py-1 bg-emerald-800 hover:bg-emerald-700 rounded-lg text-xs flex items-center gap-1 transition-colors">
                    <RefreshCcw size={11} /> آپدیت
                  </button>
                )}
                <button onClick={() => { addToDashboard(expandedSym) }}
                  title="افزودن به داشبورد شخصی"
                  className="px-2.5 py-1 bg-indigo-800 hover:bg-indigo-700 rounded-lg text-xs transition-colors">
                  + داشبورد
                </button>
                <button onClick={() => setExpandedTableMode(v => !v)}
                  title={expandedTableMode ? 'نمایش نمودار' : 'نمایش جدول'}
                  className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${expandedTableMode ? 'bg-cyan-700' : 'bg-slate-800 hover:bg-slate-700'}`}>
                  {expandedTableMode ? '📈 نمودار' : '📋 جدول'}
                </button>
                <button onClick={() => { setExpandedOpen(false); setExpandedSym2(''); setExpandedData2([]); setExpandedTableMode(false) }}
                  className="px-2.5 py-1 bg-rose-800 hover:bg-rose-700 rounded-lg text-xs transition-colors">
                  <Minimize2 size={13} />
                </button>
              </div>
            </div>

            {/* stats row */}
            <div className="px-4 py-2 border-b border-slate-800/50 bg-slate-950/30 flex items-center gap-4 text-xs flex-wrap">
              {expandedFiltered.length > 0 && (
                <>
                  <span className="text-cyan-300">آخرین: {fmtFull(expandedFiltered[expandedFiltered.length - 1].value)}</span>
                  {expandedAvg != null && <span className="text-amber-400">میانگین: {fmtFull(expandedAvg)}</span>}
                  {expandedStats.min != null && <span className="text-rose-400">کمینه: {fmtFull(expandedStats.min)}</span>}
                  {expandedStats.max != null && <span className="text-emerald-400">بیشینه: {fmtFull(expandedStats.max)}</span>}
                  <span className="text-slate-600">{expandedFiltered.length} نقطه</span>
                  <span className="text-slate-700">{expandedFiltered[0]?.date} → {expandedFiltered.at(-1)?.date}</span>
                </>
              )}
              {expandedSym2 && expandedData2.length > 0 && (
                <span className="text-purple-400">
                  {expandedSym2}: {fmtFull(filterByRange(expandedData2, expandedRange).at(-1)?.value)}
                </span>
              )}
            </div>

            {/* chart / table */}
            {expandedTableMode ? (
              <div className="flex-1 overflow-auto p-4 min-h-0">
                <table className="w-full text-xs text-right border-collapse">
                  <thead className="sticky top-0 bg-slate-900">
                    <tr>
                      <th className="p-2 border-b border-slate-800 text-slate-500">تاریخ</th>
                      <th className="p-2 border-b border-slate-800 text-slate-500 text-left">مقدار</th>
                      {expandedSym2 && <th className="p-2 border-b border-slate-800 text-purple-400 text-left">{expandedSym2}</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {[...expandedFiltered].reverse().map((d, i) => {
                      const v2 = expandedData2.length ? filterByRange(expandedData2, expandedRange).find(x => x.date === d.date)?.value : null
                      return (
                        <tr key={d.date} className={`border-b border-slate-800/30 ${i % 2 === 0 ? 'bg-slate-950/20' : ''}`}>
                          <td className="p-2 font-mono text-slate-400">{d.date}</td>
                          <td className="p-2 font-mono text-cyan-300 text-left">{fmtFull(d.value)}</td>
                          {expandedSym2 && <td className="p-2 font-mono text-purple-300 text-left">{v2 != null ? fmtFull(v2) : '—'}</td>}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
            <div className="flex-1 p-4 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={mergedData || expandedFiltered}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#475569" tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="left" stroke="#475569" tickFormatter={fmt} tick={{ fontSize: 10 }} width={54} />
                  {expandedSym2 && (
                    <YAxis yAxisId="right" orientation="left" stroke="#a78bfa44"
                      tickFormatter={fmt} tick={{ fontSize: 9, fill: '#a78bfa' }} width={50} />
                  )}
                  <Tooltip
                    formatter={(v, name) => [fmtFull(v), name === 'value' ? expandedSym : expandedSym2]}
                    contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }}
                  />
                  <Legend formatter={v => v === 'value' ? expandedSym : expandedSym2} />
                  {expandedAvg != null && (
                    <ReferenceLine yAxisId="left" y={expandedAvg} stroke="#f59e0b55" strokeDasharray="4 4"
                      label={{ value: 'میانگین', fill: '#f59e0b', fontSize: 10 }} />
                  )}
                  {expandedStats.max != null && (
                    <ReferenceLine yAxisId="left" y={expandedStats.max} stroke="#34d39933" strokeDasharray="2 6"
                      label={{ value: 'max', fill: '#34d399', fontSize: 9, position: 'right' }} />
                  )}
                  {expandedStats.min != null && (
                    <ReferenceLine yAxisId="left" y={expandedStats.min} stroke="#f4433633" strokeDasharray="2 6"
                      label={{ value: 'min', fill: '#f44336', fontSize: 9, position: 'right' }} />
                  )}
                  <Area yAxisId="left" dataKey="value" stroke="#22d3ee" fill="#22d3ee12" strokeWidth={2} dot={false} />
                  {expandedSym2 && (
                    <Line yAxisId="right" dataKey="value2" stroke="#a78bfa" strokeWidth={1.5} dot={false} strokeDasharray="5 3" />
                  )}
                  <Brush dataKey="date" height={20} stroke="#22d3ee22" travellerWidth={6} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            )}
          </div>
        </div>
      )}

      {/* ── Quick Search (Ctrl+K) ── */}
      {quickSearchOpen && (() => {
        const q = quickSearchQuery.toLowerCase()
        const filteredQS = quickSearchQuery.length >= 2
          ? quickSearchResults
          : symbols.filter(s => !q || s.symbol.toLowerCase().includes(q) || s.name?.toLowerCase().includes(q)).slice(0, 12)
        return (
          <div className="fixed inset-0 bg-slate-950/80 z-50 flex items-start justify-center pt-20 px-4" dir="rtl"
            onClick={() => setQuickSearchOpen(false)}>
            <div className="w-full max-w-xl bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-hidden"
              onClick={e => e.stopPropagation()}>
              <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
                <Search size={16} className="text-slate-400 shrink-0" />
                <input autoFocus value={quickSearchQuery} onChange={e => setQuickSearchQuery(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && filteredQS.length > 0) {
                      openExpanded(filteredQS[0].symbol)
                      setQuickSearchOpen(false)
                    }
                  }}
                  placeholder="جستجوی سریع نماد یا نام..." dir="rtl"
                  className="flex-1 bg-transparent text-sm outline-none placeholder-slate-600" />
                <kbd className="text-[10px] text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded">ESC</kbd>
              </div>
              {!quickSearchQuery && (
                <div className="px-4 pt-2 pb-1 flex flex-wrap gap-1">
                  {['FRED', 'YAHOO', 'WORLDBANK', 'IMF'].map(src => (
                    <button key={src} onClick={() => setQuickSearchQuery(src.toLowerCase())}
                      className="text-[10px] px-2 py-0.5 rounded-full border border-slate-700 hover:border-slate-500 text-slate-500 hover:text-slate-300 transition-colors">
                      {src}
                    </button>
                  ))}
                </div>
              )}
              <div className="max-h-80 overflow-y-auto">
                {filteredQS.map((s, idx) => {
                  const fsStatus = freshnessMap[s.symbol]?.status
                  const dotColor = { healthy: '#34d399', due_soon: '#fb923c', stale: '#f43f5e', never_updated: '#a78bfa' }[fsStatus]
                  return (
                    <div key={s.id} className={`flex items-center gap-3 px-4 py-2.5 transition-colors ${idx === 0 && quickSearchQuery ? 'bg-slate-800/60' : 'hover:bg-slate-800/40'}`}>
                      <button className="flex items-center gap-3 flex-1 text-right min-w-0"
                        onClick={() => { openExpanded(s.symbol); setQuickSearchOpen(false) }}>
                        <SourceBadge source={s.source} />
                        {dotColor && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dotColor }} />}
                        <span className="font-mono text-xs text-cyan-300 shrink-0">{s.symbol}</span>
                        <span className="text-xs text-slate-400 truncate flex-1">{s.name}</span>
                        {s.has_data && <span className="text-[10px] text-emerald-500 shrink-0">{fmt(s.data_points_count)} رکورد</span>}
                      </button>
                      <button onClick={() => { addToDashboard(s.symbol); setQuickSearchOpen(false) }}
                        title="افزودن به داشبورد"
                        className="shrink-0 w-6 h-6 flex items-center justify-center rounded bg-slate-800 hover:bg-indigo-700 text-slate-500 hover:text-white transition-colors text-xs">+</button>
                    </div>
                  )
                })}
                {quickSearchLoading && (
                  <div className="py-4 text-center text-slate-600 text-xs animate-pulse">در حال جستجو...</div>
                )}
                {!quickSearchLoading && quickSearchQuery && filteredQS.length === 0 && (
                  <div className="py-8 text-center text-slate-700 text-sm">نتیجه‌ای پیدا نشد</div>
                )}
                {!quickSearchQuery && symbols.length === 0 && (
                  <div className="py-8 text-center text-slate-700 text-sm">شاخصی در پایگاه داده نیست</div>
                )}
              </div>
              <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[10px] text-slate-600">↵ باز کردن نمودار · + افزودن به داشبورد</span>
                <span className="text-[10px] text-slate-600">⌘K برای باز/بستن</span>
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}

// ── Lab Panel ─────────────────────────────────────────────
function LabPanel({ symbols, API_BASE, setMessage }) {
  const [variables, setVariables] = useState([
    { id: 'A', symbol: '', data: [] },
    { id: 'B', symbol: '', data: [] },
  ])
  const [labMode, setLabMode] = useState('formula') // 'formula' | 'correlate'
  const [formula, setFormula] = useState('A / B * 100')
  const [labResult, setLabResult] = useState([])
  const [labSeries, setLabSeries] = useState({})
  const [corrResult, setCorrResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [labRange, setLabRange] = useState('ALL')
  const [savedFormulas, setSavedFormulas] = useState(() => {
    try { return JSON.parse(localStorage.getItem('saved_lab_formulas') || '[]') } catch { return [] }
  })
  const [showSavedFormulas, setShowSavedFormulas] = useState(false)

  const saveFormula = () => {
    if (!formula.trim()) return
    const entry = { formula: formula.trim(), date: new Date().toLocaleDateString('fa-IR') }
    const next = [entry, ...savedFormulas.filter(f => f.formula !== entry.formula)].slice(0, 20)
    setSavedFormulas(next)
    localStorage.setItem('saved_lab_formulas', JSON.stringify(next))
  }

  const deleteFormula = (f) => {
    const next = savedFormulas.filter(sf => sf.formula !== f)
    setSavedFormulas(next)
    localStorage.setItem('saved_lab_formulas', JSON.stringify(next))
  }

  const loadVar = useCallback(async (varId, sym) => {
    if (!sym) return
    setVariables(p => p.map(v => v.id === varId ? { ...v, loading: true, error: null } : v))
    try {
      const r = await axios.get(`${API_BASE}/data/${sym}`)
      const data = r.data?.data || []
      setVariables(p => p.map(v => v.id === varId ? { ...v, data, loading: false, error: data.length === 0 ? 'بدون داده' : null } : v))
    } catch (e) {
      setVariables(p => p.map(v => v.id === varId ? { ...v, loading: false, error: extractErrorMessage(e, 'خطا در بارگذاری') } : v))
    }
  }, [API_BASE])

  const changeSym = (varId, sym) => {
    setVariables(p => p.map(v => v.id === varId ? { ...v, symbol: sym, data: [], loading: false, error: null } : v))
    if (sym) loadVar(varId, sym)
  }

  const addVar = () => {
    const id = String.fromCharCode(65 + variables.length)
    setVariables(p => [...p, { id, symbol: '', data: [] }])
  }

  const removeVar = (id) => setVariables(p => p.filter(v => v.id !== id))

  const runCompute = async () => {
    const payload = {}
    for (const v of variables) {
      if (!v.symbol) return setMessage('برای همه متغیرها نماد انتخاب کن.', 'warning')
      payload[v.id] = v.symbol
    }
    setRunning(true)
    if (labMode === 'correlate') {
      try {
        const r = await axios.post(`${API_BASE}/data/lab/correlate`, { formula: '', variables: payload })
        setCorrResult(r.data); setLabResult([]); setLabSeries({})
        setMessage(`همبستگی محاسبه شد. ${r.data.n_observations} نقطه مشترک.`, 'success')
      } catch (e) {
        setMessage(e?.response?.data?.detail || 'خطا در محاسبه همبستگی.', 'error')
        setCorrResult(null)
      } finally { setRunning(false) }
      return
    }
    setCorrResult(null)
    try {
      const r = await axios.post(`${API_BASE}/data/lab/compute`, { formula, variables: payload })
      setLabResult(r.data?.result || [])
      setLabSeries(r.data?.series || {})
      if (!r.data?.result?.length) setMessage('نتیجه‌ای تولید نشد.', 'warning')
    } catch (e) {
      setMessage(e?.response?.data?.detail || 'خطا در محاسبه فرمول.', 'error')
    } finally { setRunning(false) }
  }

  const resultInRange = useMemo(() => filterByRange(labResult, labRange), [labResult, labRange])
  const stats = useMemo(() => {
    const vs = resultInRange.map(d => d.value).filter(Number.isFinite)
    if (!vs.length) return null
    return { min: Math.min(...vs), max: Math.max(...vs), avg: vs.reduce((a, b) => a + b) / vs.length, last: vs.at(-1) }
  }, [resultInRange])

  const dataSymbols = useMemo(() => symbols.filter(s => s.has_data), [symbols])

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        <FlaskConical size={18} className="text-purple-400" /> آزمایشگاه شاخص‌های اقتصادی
      </h2>

      {/* Mode toggle */}
      <div className="flex gap-1 bg-slate-900 rounded-xl p-1 w-fit">
        {[['formula', 'فرمول سازی'], ['correlate', 'همبستگی']].map(([k, l]) => (
          <button key={k} onClick={() => setLabMode(k)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${labMode === k ? 'bg-purple-700 text-white' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'}`}>
            {l}
          </button>
        ))}
      </div>

      {/* Variables */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {variables.map((v, i) => (
          <div key={v.id} className="bg-slate-900 border border-slate-800 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-sm" style={{ color: SERIES_COLORS[i % SERIES_COLORS.length] }}>
                متغیر {v.id}
              </span>
              {i >= 2 && <button onClick={() => removeVar(v.id)} className="text-xs text-rose-400 hover:text-rose-300">× حذف</button>}
            </div>
            <select value={v.symbol} onChange={e => changeSym(v.id, e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-sm outline-none">
              <option value="">انتخاب نماد...</option>
              {dataSymbols.map(s => <option key={s.id} value={s.symbol}>{s.symbol} — {s.name?.slice(0, 35)}</option>)}
            </select>
            {v.symbol && (() => {
              const sym = dataSymbols.find(s => s.symbol === v.symbol)
              return sym ? (
                <div className="flex items-center gap-1.5 text-[10px] text-slate-600">
                  <SourceBadge source={sym.source} />
                  <span className="truncate">{sym.name?.slice(0, 40)}</span>
                </div>
              ) : null
            })()}
            {v.loading ? (
              <div className="h-14 flex items-center justify-center">
                <span className="text-xs text-slate-500 animate-pulse">در حال بارگذاری...</span>
              </div>
            ) : v.error ? (
              <div className="h-14 flex items-center justify-center">
                <span className="text-xs text-rose-500">{v.error}</span>
              </div>
            ) : (
              <MiniChart data={v.data} color={SERIES_COLORS[i % SERIES_COLORS.length]} showStats />
            )}
            {!v.loading && !v.error && v.data.length > 0 && (
              <div className="text-[10px] text-slate-600 flex justify-between">
                <span>{v.data[0]?.date}</span>
                <span>{v.data.length} رکورد</span>
                <span>{v.data.at(-1)?.date}</span>
              </div>
            )}
          </div>
        ))}
        {variables.length < 6 && (
          <button onClick={addVar}
            className="border-2 border-dashed border-slate-800 hover:border-slate-600 rounded-xl p-3 text-slate-600 hover:text-slate-400 text-sm transition-colors">
            + افزودن متغیر
          </button>
        )}
      </div>

      {/* Templates */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 space-y-2">
        <div className="text-xs text-slate-500">قالب‌های آماده:</div>
        <div className="flex flex-wrap gap-1.5">
          {FORMULA_TEMPLATES.map(t => (
            <button key={t.label} onClick={() => { setFormula(t.formula); setMessage(`«${t.label}»: ${t.hint}`, 'info') }}
              title={t.hint}
              className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs text-slate-300 hover:text-white transition-colors">
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Formula input (formula mode only) */}
      {labMode === 'formula' && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <div className="flex-1 bg-slate-900 border border-slate-700 focus-within:border-purple-600 rounded-xl px-4 py-2.5 flex items-center gap-2 transition-colors">
              <span className="text-slate-500 font-mono text-sm shrink-0">f =</span>
              <input value={formula} onChange={e => setFormula(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runCompute()}
                className="flex-1 bg-transparent font-mono text-sm outline-none text-purple-300 placeholder-slate-700"
                placeholder="مثال: A / B * 100" />
            </div>
            <button onClick={saveFormula} title="ذخیره فرمول"
              className="px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-xl text-sm transition-colors">💾</button>
            <button onClick={() => setShowSavedFormulas(v => !v)} title="فرمول‌های ذخیره‌شده"
              className={`px-3 py-2 rounded-xl text-sm transition-colors relative ${showSavedFormulas ? 'bg-purple-800' : 'bg-slate-800 hover:bg-slate-700'}`}>
              📋
              {savedFormulas.length > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-purple-600 rounded-full text-[9px] flex items-center justify-center">{savedFormulas.length}</span>
              )}
            </button>
            <button onClick={runCompute} disabled={running}
              className="px-5 py-2 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 rounded-xl text-sm font-semibold transition-colors">
              {running ? <span className="animate-pulse">...</span> : 'محاسبه'}
            </button>
          </div>
          {showSavedFormulas && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 space-y-1.5">
              <div className="text-[11px] text-slate-500 mb-1">فرمول‌های ذخیره‌شده:</div>
              {savedFormulas.length === 0 && (
                <div className="text-[11px] text-slate-700">هنوز فرمولی ذخیره نشده است. روی 💾 کلیک کنید.</div>
              )}
              {savedFormulas.map(sf => (
                <div key={sf.formula} className="flex items-center gap-2 group">
                  <button onClick={() => { setFormula(sf.formula); setShowSavedFormulas(false) }}
                    className="flex-1 text-right font-mono text-xs text-purple-300 hover:text-purple-200 bg-slate-800 hover:bg-slate-700 rounded-lg px-3 py-1.5 transition-colors">
                    {sf.formula}
                  </button>
                  <span className="text-[10px] text-slate-700 shrink-0">{sf.date}</span>
                  <button onClick={() => deleteFormula(sf.formula)}
                    className="text-slate-700 hover:text-rose-400 transition-colors text-xs opacity-0 group-hover:opacity-100">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {labMode === 'correlate' && (
        <button onClick={runCompute} disabled={running}
          className="px-6 py-2.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 rounded-xl text-sm font-semibold transition-colors">
          {running ? <span className="animate-pulse">در حال محاسبه...</span> : 'محاسبه ماتریس همبستگی'}
        </button>
      )}

      <div className="text-xs text-slate-700">
        توابع: <span className="text-slate-600 font-mono">lag  pct_change  rolling_mean  rolling_std  normalize  zscore  diff  cumsum  log  abs</span>
      </div>

      {/* Results */}
      {(labResult.length > 0 || Object.keys(labSeries).length > 0) && (
        <div className="space-y-3">
          {Object.keys(labSeries).length > 0 && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(labSeries).map(([varId, data], i) => {
                const sym = variables.find(v => v.id === varId)?.symbol || varId
                return (
                  <div key={varId} className="bg-slate-900/80 border border-slate-800 rounded-xl p-3">
                    <div className="text-xs font-mono mb-1" style={{ color: SERIES_COLORS[i % SERIES_COLORS.length] }}>
                      {varId} = {sym}
                    </div>
                    <MiniChart data={data} color={SERIES_COLORS[i % SERIES_COLORS.length]} showStats />
                  </div>
                )
              })}
            </div>
          )}

          <div className="bg-slate-900 border border-purple-900/40 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-purple-300">نتیجه:</span>
                <code className="text-xs font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-400">{formula}</code>
              </div>
              <div className="flex items-center gap-1">
                {CHART_RANGES.map(r => (
                  <button key={r.key} onClick={() => setLabRange(r.key)}
                    className={`px-2 py-1 rounded text-xs transition-colors ${labRange === r.key ? 'bg-purple-700' : 'bg-slate-800 hover:bg-slate-700'}`}>
                    {r.label}
                  </button>
                ))}
                <button onClick={() => exportCSV(resultInRange, `lab_result`)}
                  className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-xs flex items-center gap-1 transition-colors">
                  <Download size={11} /> CSV
                </button>
              </div>
            </div>

            {stats && (
              <div className="grid grid-cols-4 gap-2">
                {[['آخرین', stats.last], ['میانگین', stats.avg], ['کمینه', stats.min], ['بیشینه', stats.max]].map(([l, v]) => (
                  <div key={l} className="bg-slate-800 rounded-xl py-2 text-center">
                    <div className="text-[10px] text-slate-500">{l}</div>
                    <div className="text-xs text-slate-200 font-mono font-semibold mt-0.5">{fmtFull(v)}</div>
                  </div>
                ))}
              </div>
            )}

            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={resultInRange}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" stroke="#475569" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#475569" tickFormatter={fmt} width={52} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={fmtFull} contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
                  {stats?.avg != null && (
                    <ReferenceLine y={stats.avg} stroke="#a78bfa55" strokeDasharray="4 4"
                      label={{ value: 'میانگین', fill: '#a78bfa', fontSize: 10 }} />
                  )}
                  <Area dataKey="value" stroke="#c084fc" fill="#c084fc12" dot={false} strokeWidth={2} />
                  <Brush dataKey="date" height={20} stroke="#7e22ce44" travellerWidth={8} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="text-xs text-slate-700 text-left">{resultInRange.length} نقطه</div>
          </div>
        </div>
      )}

      {labResult.length === 0 && Object.keys(labSeries).length === 0 && !corrResult && (
        <div className="h-40 bg-slate-900/40 border-2 border-dashed border-slate-800 rounded-xl flex flex-col items-center justify-center text-slate-700 text-sm gap-2">
          <FlaskConical size={28} className="opacity-20" />
          {labMode === 'formula' ? 'متغیرها را انتخاب کن، فرمول بنویس و محاسبه را بزن' : 'متغیرها را انتخاب کن و ماتریس همبستگی را محاسبه کن'}
        </div>
      )}

      {/* Correlation results */}
      {corrResult && (
        <div className="bg-slate-900 border border-purple-900/40 rounded-xl p-4 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-purple-300">ماتریس همبستگی پیرسون</span>
            <span className="text-xs text-slate-500">{corrResult.n_observations} نقطه مشترک</span>
          </div>
          <div className="overflow-auto">
            <table className="text-xs w-full border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-slate-600"></th>
                  {Object.keys(corrResult.variables).map(k => (
                    <th key={k} className="p-2 text-slate-400 font-mono">{k} ({corrResult.variables[k]?.slice(0,12)})</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.keys(corrResult.variables).map(rowVar => (
                  <tr key={rowVar}>
                    <td className="p-2 text-slate-400 font-mono font-bold">{rowVar}</td>
                    {Object.keys(corrResult.variables).map(colVar => {
                      const cell = corrResult.matrix.find(m => m.a === rowVar && m.b === colVar)
                      const val = cell?.corr
                      const abs = Math.abs(val ?? 0)
                      const isStrong = abs > 0.7
                      const isMod = abs > 0.4
                      const bg = val === 1 ? '#1e293b' : isStrong ? (val > 0 ? '#065f46' : '#7f1d1d') : isMod ? (val > 0 ? '#14532d' : '#450a0a') : '#1e293b'
                      const color = val == null ? '#475569' : val === 1 ? '#94a3b8' : isStrong ? '#86efac' : isMod ? '#6ee7b7' : '#94a3b8'
                      return (
                        <td key={colVar} className="p-2 text-center rounded"
                          style={{ background: bg, color }}>
                          {val != null ? val.toFixed(3) : '—'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-[10px] text-slate-600">
            رنگ سبز = همبستگی مثبت قوی | رنگ قرمز = همبستگی منفی قوی | &gt;0.7 قوی، 0.4-0.7 متوسط
          </div>

          {/* Scatter plots for each pair */}
          {corrResult.scatter && Object.entries(corrResult.scatter).length > 0 && (
            <div>
              <div className="text-[11px] text-slate-500 mb-2">نمودار پراکندگی جفت‌ها:</div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(corrResult.scatter).map(([pairKey, data], i) => {
                  const [a, b] = pairKey.split('_')
                  const corr = corrResult.matrix.find(m => m.a === a && m.b === b)?.corr
                  const clr = SERIES_COLORS[i % SERIES_COLORS.length]
                  return (
                    <div key={pairKey} className="bg-slate-950 border border-slate-800 rounded-xl p-3">
                      <div className="text-[11px] font-mono mb-1 flex justify-between">
                        <span style={{ color: clr }}>{a} vs {b}</span>
                        {corr != null && <span className={Math.abs(corr) > 0.7 ? 'text-emerald-400' : 'text-slate-500'}>r={corr}</span>}
                      </div>
                      <div className="h-40">
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                            <XAxis dataKey="x" name={a} stroke="#475569" tick={{ fontSize: 9 }} tickFormatter={fmt} />
                            <YAxis dataKey="y" name={b} stroke="#475569" tick={{ fontSize: 9 }} tickFormatter={fmt} width={42} />
                            <ZAxis range={[20, 20]} />
                            <Tooltip cursor={{ strokeDasharray: '3 3' }}
                              formatter={(v, name) => [fmtFull(v), name]}
                              contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 10 }} />
                            <Scatter data={data.slice(0, 500)} fill={clr} fillOpacity={0.6} />
                          </ScatterChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

// ── Sources Panel ─────────────────────────────────────────
function SourcesPanel({ summary, freshness, runPipeline, setMessage }) {
  const [busy, setBusy] = useState({})

  const sourceStats = useMemo(() => {
    const m = {}
    for (const s of summary?.sources || []) m[s.source] = s
    return m
  }, [summary])

  const staleBySource = useMemo(() => {
    const m = {}
    for (const item of freshness?.items || []) {
      if (item.status === 'stale') m[item.source] = (m[item.source] || 0) + 1
    }
    return m
  }, [freshness])

  const discover = async (cfg) => {
    if (!cfg.discoverPath) return setMessage(`${cfg.label} نیاز به کانفیگ دستی دارد.`, 'warning')
    setBusy(b => ({ ...b, [cfg.key]: true }))
    try { await runPipeline(cfg.discoverPath, `کاوش ${cfg.label} آغاز شد.`) }
    finally { setBusy(b => ({ ...b, [cfg.key]: false })) }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">منابع داده جهانی (۱۴ منبع)</h2>
        <button onClick={() => runPipeline('/discover/auto-spider?source=ALL', 'کاوش همه ۱۴ منبع آغاز شد.')}
          className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 rounded-xl text-sm font-semibold transition-colors">
          🌍 کاوش همه
        </button>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {SOURCE_CONFIGS.map(cfg => {
          const s = sourceStats[cfg.key]
          const total = s?.indicators ?? 0
          const withData = s?.indicators_with_data ?? 0
          const cov = total > 0 ? Math.round((withData / total) * 100) : 0
          return (
            <div key={cfg.key}
              className="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4 space-y-3 hover:border-slate-600 transition-colors"
              style={{ borderLeftWidth: 2, borderLeftColor: cfg.color }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold text-sm">{cfg.label}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{cfg.desc}</div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono shrink-0"
                  style={{ background: cfg.color + '22', color: cfg.color }}>{cfg.key}</span>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">{total} شاخص</span>
                  <div className="flex items-center gap-2">
                    {s?.data_points > 0 && <span className="text-[10px] text-slate-600">{fmt(s.data_points)} رکورد</span>}
                    <span style={{ color: withData > 0 ? cfg.color : '#475569' }}>{cov}%</span>
                  </div>
                </div>
                <div className="bg-slate-800 rounded-full h-1.5">
                  <div className="h-full rounded-full transition-all" style={{ width: `${cov}%`, background: cfg.color }} />
                </div>
                <div className="flex justify-between text-[10px] text-slate-700">
                  <span>{withData} دارای داده</span>
                  {total - withData > 0 && <span>{total - withData} خالی</span>}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-600">هر {cfg.interval}</span>
                  {staleBySource[cfg.key] > 0 && (
                    <span className="text-[10px] bg-rose-900/50 text-rose-400 px-1.5 py-0.5 rounded-full">
                      {staleBySource[cfg.key]} دیرهنگام
                    </span>
                  )}
                </div>
                <button disabled={!cfg.discoverPath || busy[cfg.key]} onClick={() => discover(cfg)}
                  className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-40 rounded-lg text-xs transition-colors">
                  {busy[cfg.key] ? <span className="animate-pulse">در حال کاوش...</span> : 'کاوش'}
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl p-4 grid sm:grid-cols-3 gap-3 text-xs">
        {[
          { step: '۱', title: 'کاوش', color: 'text-emerald-400', text: 'دکمه «کاوش همه» یا کاوش هر منبع جداگانه را بزن' },
          { step: '۲', title: 'دریافت داده', color: 'text-cyan-400', text: 'از تب مدیریت، دریافت فوری هر شاخص را بزن' },
          { step: '۳', title: 'داشبورد', color: 'text-indigo-400', text: 'شاخص‌ها را به داشبورد شخصی‌ات اضافه کن' },
        ].map(({ step, title, color, text }) => (
          <div key={step} className="bg-slate-950 rounded-xl p-3">
            <div className={`font-semibold mb-1 ${color}`}>مرحله {step}: {title}</div>
            <p className="text-slate-400">{text}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Login View ────────────────────────────────────────────
function LoginView({ users, loginUserId, setLoginUserId, login, newUsername, setNewUsername, newDisplayName, setNewDisplayName, addUser, backendOk, msg }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900 text-slate-100 flex items-center justify-center p-6" dir="rtl">
      <div className="max-w-4xl w-full space-y-6">
        <div className="text-center space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center mx-auto shadow-2xl shadow-cyan-500/20">
            <Activity size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-l from-cyan-300 to-blue-400 bg-clip-text text-transparent">
            پنل اقتصاد جهانی
          </h1>
          <p className="text-slate-500 text-sm">جمع‌آوری و تحلیل داده از ۱۴ منبع بین‌المللی</p>
          <div className="flex items-center justify-center gap-2">
            <span className={`w-2 h-2 rounded-full ${backendOk === false ? 'bg-rose-500' : 'bg-emerald-400 animate-pulse'}`} />
            <span className={`text-xs ${backendOk === false ? 'text-rose-400' : 'text-emerald-400'}`}>
              {backendOk === false ? 'سرور در دسترس نیست' : 'سرور آماده است'}
            </span>
          </div>
          <div className="flex flex-wrap justify-center gap-1.5 max-w-lg mx-auto">
            {SOURCE_CONFIGS.map(s => (
              <span key={s.key}
                className="text-[10px] px-2 py-0.5 rounded-full font-mono"
                style={{ background: s.color + '22', color: s.color, border: `1px solid ${s.color}44` }}>
                {s.label}
              </span>
            ))}
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <h2 className="font-bold flex items-center gap-2"><Users size={16} /> ورود به حساب</h2>
            {users.length === 0
              ? <p className="text-sm text-slate-500">ابتدا یک حساب کاربری بساز.</p>
              : <select value={loginUserId} onChange={e => setLoginUserId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 focus:border-cyan-600 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors">
                  <option value="">انتخاب کاربر...</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.display_name} ({u.username})</option>)}
                </select>}
            <button onClick={login} disabled={!loginUserId}
              className="w-full bg-cyan-700 hover:bg-cyan-600 disabled:opacity-40 rounded-xl py-2.5 text-sm font-semibold transition-colors">
              ورود
            </button>
            {msg?.text && <div className="text-xs text-slate-400">{msg.text}</div>}
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <h3 className="font-semibold flex items-center gap-2"><UserPlus size={15} /> ساخت حساب جدید</h3>
            <input value={newUsername} onChange={e => setNewUsername(e.target.value)} placeholder="username"
              className="w-full bg-slate-950 border border-slate-700 focus:border-cyan-600 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors" />
            <input value={newDisplayName} onChange={e => setNewDisplayName(e.target.value)} placeholder="نام نمایشی"
              onKeyDown={e => e.key === 'Enter' && addUser()}
              className="w-full bg-slate-950 border border-slate-700 focus:border-cyan-600 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors" />
            <button onClick={addUser}
              className="w-full bg-emerald-700 hover:bg-emerald-600 rounded-xl py-2.5 text-sm font-semibold transition-colors">
              ایجاد کاربر
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
