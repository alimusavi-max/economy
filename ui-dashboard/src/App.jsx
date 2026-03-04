import { useCallback, useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import {
  Area,
  AreaChart,
  Brush,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'
import {
  Activity,
  FlaskConical,
  LogOut,
  Maximize2,
  Minimize2,
  RefreshCcw,
  Search,
  SlidersHorizontal,
  UserPlus,
  Users,
  WandSparkles
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const ACTIVE_USER_STORAGE_KEY = 'economy_active_user_id'

const CHART_RANGES = [
  { key: '1M', label: '۱ ماه', days: 31 },
  { key: '3M', label: '۳ ماه', days: 93 },
  { key: '1Y', label: '۱ سال', days: 366 },
  { key: '5Y', label: '۵ سال', days: 365 * 5 },
  { key: 'ALL', label: 'کل', days: Infinity }
]

const extractErrorMessage = (err, fallback) => err?.response?.data?.detail || err?.message || fallback
const formatCompactNumber = (value) => Intl.NumberFormat('fa-IR', { notation: 'compact', maximumFractionDigits: 2 }).format(value || 0)
const formatPreciseNumber = (value) => Intl.NumberFormat('fa-IR', { maximumFractionDigits: 4 }).format(value || 0)
const sourceSupportsManualRefresh = (source) => ['FRED', 'YAHOO', 'WORLDBANK', 'ECB', 'DBNOMICS', 'IMF', 'OECD', 'BIS', 'EUROSTAT', 'ALPHAVANTAGE'].includes(source)

const withRetry = async (fn, retries = 1) => {
  let lastErr
  for (let i = 0; i <= retries; i += 1) {
    try {
      return await fn()
    } catch (err) {
      lastErr = err
    }
  }
  throw lastErr
}

const filterChartByRange = (data, rangeKey) => {
  const range = CHART_RANGES.find((r) => r.key === rangeKey) || CHART_RANGES.at(-1)
  if (!data?.length || !Number.isFinite(range.days)) return data || []
  const lastTs = new Date(data[data.length - 1].date).getTime()
  const minTs = lastTs - range.days * 24 * 60 * 60 * 1000
  return data.filter((item) => new Date(item.date).getTime() >= minTs)
}

export default function App() {
  const [summary, setSummary] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [activeTab, setActiveTab] = useState('dashboard')
  const [sourceFilter, setSourceFilter] = useState('')
  const [dbnomicsProviderFilter, setDbnomicsProviderFilter] = useState('')
  const [dbnomicsProviderSearch, setDbnomicsProviderSearch] = useState('')
  const [dbnomicsProviders, setDbnomicsProviders] = useState([])
  const [search, setSearch] = useState('')
  const [withDataOnly, setWithDataOnly] = useState(false)
  const [symbolsPage, setSymbolsPage] = useState(1)
  const [symbolsPageSize, setSymbolsPageSize] = useState(50)
  const [symbolsTotalPages, setSymbolsTotalPages] = useState(1)
  const [symbolsTotal, setSymbolsTotal] = useState(0)

  const [symbolsPage, setSymbolsPage] = useState(1)
  const [symbolsPageSize, setSymbolsPageSize] = useState(100)
  const [symbolsTotalPages, setSymbolsTotalPages] = useState(1)
  const [symbolsTotal, setSymbolsTotal] = useState(0)

  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [loginUserId, setLoginUserId] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [defaultDashboardSymbols, setDefaultDashboardSymbols] = useState([])
  const [dashboardCharts, setDashboardCharts] = useState([])
  const [dashboardRanges, setDashboardRanges] = useState({})

  const [expandedChartOpen, setExpandedChartOpen] = useState(false)
  const [expandedChartSymbol, setExpandedChartSymbol] = useState('')
  const [expandedChartData, setExpandedChartData] = useState([])
  const [expandedChartRange, setExpandedChartRange] = useState('ALL')

  const [variables, setVariables] = useState([{ id: 'A', symbol: '' }, { id: 'B', symbol: '' }])
  const [formula, setFormula] = useState('(A / B) * 100')
  const [labData, setLabData] = useState([])
  const [backendConnected, setBackendConnected] = useState(null)

  const activeUser = useMemo(() => users.find((u) => String(u.id) === String(selectedUserId)) || null, [users, selectedUserId])
  const isLoggedIn = !!activeUser

  const fetchSymbolChart = useCallback(async (symbol) => {
    const res = await withRetry(() => axios.get(`${API_BASE}/data/${symbol}`), 1)
    return res.data?.data || []
  }, [])

  const loadUsers = useCallback(async () => {
    const res = await axios.get(`${API_BASE}/users`)
    const allUsers = res.data || []
    setUsers(allUsers)

    const storedUserId = localStorage.getItem(ACTIVE_USER_STORAGE_KEY)
    if (storedUserId && allUsers.some((u) => String(u.id) === storedUserId)) {
      setSelectedUserId(storedUserId)
      setLoginUserId(storedUserId)
      return
    }

    if (!storedUserId && !loginUserId && allUsers.length) {
      const firstId = String(allUsers[0].id)
      setLoginUserId(firstId)
      if (!selectedUserId) setSelectedUserId(firstId)
    }
  }, [loginUserId, selectedUserId])

  const loadDbnomicsProviders = useCallback(async () => {
    if (sourceFilter !== 'DBNOMICS') return
    try {
      const params = { limit: 20000 }
      if (dbnomicsProviderSearch.trim()) params.search = dbnomicsProviderSearch.trim()
      if (withDataOnly) params.with_data_only = true
      const res = await axios.get(`${API_BASE}/data/dbnomics/providers`, { params })
      setDbnomicsProviders(res.data || [])
    } catch {
      setDbnomicsProviders([])
    }
  }, [dbnomicsProviderSearch, sourceFilter, withDataOnly])

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        paginated: true,
        page: symbolsPage,
        page_size: symbolsPageSize,
        limit: 10000
      }
      if (sourceFilter) params.source = sourceFilter
      if (dbnomicsProviderFilter && sourceFilter === 'DBNOMICS') params.dbnomics_provider = dbnomicsProviderFilter
      if (search.trim()) params.search = search.trim()
      if (withDataOnly) params.with_data_only = true

      const [summaryRes, freshnessRes, symbolsRes] = await Promise.all([
        axios.get(`${API_BASE}/data/summary`),
        axios.get(`${API_BASE}/data/freshness`),
        axios.get(`${API_BASE}/data/symbols/available`, { params })
      ])

      setSummary(summaryRes.data)
      setFreshness(freshnessRes.data)
      setSymbols(symbolsRes.data?.items || [])
      setSymbolsTotal(symbolsRes.data?.pagination?.total || 0)
      setSymbolsTotalPages(symbolsRes.data?.pagination?.total_pages || 1)
      setBackendConnected(true)
      setMessage('')
    } catch (err) {
      setBackendConnected(false)
      setSummary(null)
      setFreshness(null)
      setSymbols([])
      setMessage(extractErrorMessage(err, 'خطا در بارگذاری داشبورد.'))
    } finally {
      setLoading(false)
    }
  }, [dbnomicsProviderFilter, search, sourceFilter, symbolsPage, symbolsPageSize, withDataOnly])

  const loadUserDashboard = useCallback(async (userId) => {
    if (!userId) return
    try {
      const res = await axios.get(`${API_BASE}/users/${userId}/dashboard`)
      const symbolsFromUser = res.data?.symbols || []
      setDefaultDashboardSymbols(symbolsFromUser)

      const chartPromises = symbolsFromUser.slice(0, 12).map(async (sym) => {
        try {
          const data = await fetchSymbolChart(sym)
          return { symbol: sym, data, error: null }
        } catch (err) {
          return { symbol: sym, data: [], error: extractErrorMessage(err, 'داده دریافت نشد') }
        }
      })

      setDashboardCharts(await Promise.all(chartPromises))
    } catch {
      setDefaultDashboardSymbols([])
      setDashboardCharts([])
    }
  }, [fetchSymbolChart])

  useEffect(() => { Promise.all([loadUsers(), loadDashboard()]).catch(() => null) }, [loadDashboard, loadUsers])
  useEffect(() => { if (sourceFilter === 'DBNOMICS') loadDbnomicsProviders().catch(() => null); else { setDbnomicsProviderFilter(''); setDbnomicsProviders([]) } }, [loadDbnomicsProviders, sourceFilter])
  useEffect(() => { if (selectedUserId) loadUserDashboard(selectedUserId) }, [loadUserDashboard, selectedUserId])

  const persistDashboardSymbols = useCallback(async (nextSymbols, successMessage) => {
    if (!selectedUserId) return setMessage('ابتدا وارد حساب کاربری خودت شو.')
    try {
      await axios.put(`${API_BASE}/users/${selectedUserId}/dashboard`, { symbols: nextSymbols })
      setDefaultDashboardSymbols(nextSymbols)
      await loadUserDashboard(selectedUserId)
      if (successMessage) setMessage(successMessage)
    } catch (err) {
      setMessage(extractErrorMessage(err, 'ذخیره داشبورد ناموفق بود.'))
    }
  }, [loadUserDashboard, selectedUserId])

  const runPipeline = async (path, successMessage) => {
    try {
      await axios.post(`${API_BASE}${path}`)
      setMessage(successMessage)
      await loadDashboard()
      if (selectedUserId) await loadUserDashboard(selectedUserId)
    } catch (err) {
      setMessage(extractErrorMessage(err, 'ارسال دستور انجام نشد.'))
    }
  }

  const changeInterval = async (symbol, newDays) => {
    if (!newDays || newDays < 1) return
    await axios.put(`${API_BASE}/data/symbols/${symbol}/interval`, { update_interval_days: Number(newDays) })
    await loadDashboard()
  }

  const refreshNow = async (symbol) => {
    try {
      await axios.post(`${API_BASE}/data/symbols/${symbol}/refresh-now`)
      setMessage(`دریافت فوری ${symbol} انجام شد.`)
      await loadDashboard()
      if (selectedUserId) await loadUserDashboard(selectedUserId)
      if (selectedSymbol === symbol) setChartData(await fetchSymbolChart(symbol))
    } catch (err) {
      setMessage(extractErrorMessage(err, 'رفرش فوری ناموفق بود.'))
    }
  }

  const openExpandedChart = async (symbol, initialData = null) => {
    setExpandedChartSymbol(symbol)
    setExpandedChartRange('ALL')
    setExpandedChartOpen(true)
    if (initialData?.length) {
      setExpandedChartData(initialData)
      return
    }
    try {
      setExpandedChartData(await fetchSymbolChart(symbol))
    } catch {
      setExpandedChartData([])
    }
  }

  const addUser = async () => {
    try {
      const res = await axios.post(`${API_BASE}/users`, { username: newUsername, display_name: newDisplayName })
      setNewUsername(''); setNewDisplayName(''); await loadUsers()
      const createdUserId = String(res.data?.id || '')
      if (createdUserId) setLoginUserId(createdUserId)
      setMessage('کاربر جدید ساخته شد.')
    } catch (err) {
      setMessage(extractErrorMessage(err, 'ساخت کاربر ناموفق بود.'))
    }
  }

  const login = async () => {
    if (!loginUserId) return setMessage('یک کاربر انتخاب کن.')
    setSelectedUserId(loginUserId)
    localStorage.setItem(ACTIVE_USER_STORAGE_KEY, String(loginUserId))
    setActiveTab('dashboard')
    await loadUserDashboard(loginUserId)
    setMessage('ورود با موفقیت انجام شد.')
  }

  const logout = () => {
    setSelectedUserId('')
    setDefaultDashboardSymbols([])
    setDashboardCharts([])
    localStorage.removeItem(ACTIVE_USER_STORAGE_KEY)
    setMessage('خروج انجام شد.')
  }

  const addSymbolToDashboard = async (symbol) => {
    if (defaultDashboardSymbols.includes(symbol)) return
    if (defaultDashboardSymbols.length >= 12) return setMessage('حداکثر ۱۲ نماد می‌توانی برای داشبورد انتخاب کنی.')
    await persistDashboardSymbols([...defaultDashboardSymbols, symbol], `${symbol} به داشبوردت اضافه شد.`)
  }

  const removeSymbolFromDashboard = async (symbol) => {
    await persistDashboardSymbols(defaultDashboardSymbols.filter((item) => item !== symbol), `${symbol} از داشبورد حذف شد.`)
  }

  const runFormula = async () => {
    const variablesPayload = {}
    for (const v of variables) { if (!v.symbol) return setMessage('برای همه متغیرها نماد انتخاب کن.'); variablesPayload[v.id] = v.symbol }
    try {
      const res = await axios.post(`${API_BASE}/data/lab/formula`, { formula, variables: variablesPayload })
      setLabData(res.data || [])
      if (!res.data?.length) setMessage('داده مشترک برای این ترکیب پیدا نشد.')
    } catch (err) { setMessage(extractErrorMessage(err, 'فرمول معتبر نیست یا دیتای کافی وجود ندارد.')) }
  }

  const availableSources = useMemo(() => (summary?.sources || []).map((s) => s.source), [summary])
  const expandedRangeData = useMemo(() => filterChartByRange(expandedChartData, expandedChartRange), [expandedChartData, expandedChartRange])
  const expandedAverage = useMemo(() => {
    const values = expandedRangeData.map((item) => Number(item.value)).filter((item) => Number.isFinite(item))
    return values.length ? values.reduce((sum, val) => sum + val, 0) / values.length : null
  }, [expandedRangeData])

  if (!isLoggedIn) {
    return <LoginView {...{ users, loginUserId, setLoginUserId, login, newUsername, setNewUsername, newDisplayName, setNewDisplayName, addUser, backendConnected, message }} />
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 p-6" dir="rtl">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2"><Activity className="text-cyan-400" /> پنل اقتصاد جهانی</h1>
            <p className="text-slate-400 text-sm">کاربر: <span className="text-cyan-300">{activeUser?.display_name}</span> ({activeUser?.username})</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button className="px-4 py-2 bg-slate-800 rounded-lg" onClick={loadDashboard}><RefreshCcw size={16} className="inline ml-1" /> رفرش</button>
            <button className="px-4 py-2 bg-cyan-700 rounded-lg" onClick={() => runPipeline('/pipeline/trigger-all', 'دریافت موازی داده‌ها شروع شد.')}>دریافت سریع</button>
            <button className="px-4 py-2 bg-fuchsia-700 rounded-lg" onClick={() => runPipeline('/discover/dbnomics', 'کاوش بانک‌های مرکزی DBNOMICS آغاز شد.')}>کاوش بانک‌های مرکزی</button>
            <button className="px-4 py-2 bg-rose-700 rounded-lg" onClick={logout}><LogOut size={16} className="inline ml-1" /> خروج</button>
          </div>
        </header>

        {message && <div className="bg-slate-900/80 border border-slate-700 rounded-lg px-4 py-2 text-sm">{message}</div>}

        <div className="flex gap-2">
          {[['dashboard', 'داشبورد من'], ['manage', 'مدیریت شاخص‌ها'], ['users', 'تنظیمات حساب'], ['lab', 'آزمایشگاه']].map(([key, label]) => (
            <button key={key} onClick={() => setActiveTab(key)} className={`px-4 py-2 rounded-lg ${activeTab === key ? 'bg-cyan-700' : 'bg-slate-800'}`}>{label}</button>
          ))}
        </div>

        {activeTab === 'dashboard' && (
          <section className="space-y-4">
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              <StatCard title="کل شاخص‌ها" value={summary?.totals?.indicators} />
              <StatCard title="دارای داده" value={summary?.totals?.indicators_with_data} />
              <StatCard title="کل رکوردها" value={summary?.totals?.economic_data_points} />
              <StatCard title="دیرهنگام" value={freshness?.totals?.stale} />
              <StatCard title="بدون آپدیت" value={freshness?.totals?.never_updated} />
            </div>

            <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2"><Users size={16} /> داشبورد پیش‌فرض من</h3>
              {dashboardCharts.length === 0 ? (
                <div className="text-slate-400 text-sm">برای حساب شما هنوز نمودار پیش‌فرض تنظیم نشده.</div>
              ) : (
                <div className="grid lg:grid-cols-2 gap-4">
                  {dashboardCharts.map((chart) => {
                    const rangeKey = dashboardRanges[chart.symbol] || 'ALL'
                    const dataInRange = filterChartByRange(chart.data, rangeKey)
                    const lastValue = dataInRange.length ? dataInRange[dataInRange.length - 1].value : null

                    return (
                      <div key={chart.symbol} className="h-[320px] bg-slate-950 rounded-lg p-2 border border-slate-800">
                        <div className="text-xs text-slate-300 mb-2 flex items-center justify-between">
                          <span className="font-semibold">{chart.symbol}</span>
                          <span className="text-cyan-300">{lastValue !== null ? `آخرین: ${formatPreciseNumber(lastValue)}` : chart.error || 'بدون داده'}</span>
                        </div>
                        <div className="flex items-center gap-1 mb-2 flex-wrap">
                          {CHART_RANGES.map((range) => (
                            <button
                              key={range.key}
                              onClick={() => setDashboardRanges((prev) => ({ ...prev, [chart.symbol]: range.key }))}
                              className={`px-2 py-1 rounded text-[11px] ${rangeKey === range.key ? 'bg-cyan-700' : 'bg-slate-800'}`}
                            >
                              {range.label}
                            </button>
                          ))}
                          <button className="px-2 py-1 bg-indigo-700 rounded text-[11px]" onClick={() => openExpandedChart(chart.symbol, chart.data)}><Maximize2 size={12} /></button>
                          <button className="px-2 py-1 bg-rose-700 rounded text-[11px]" onClick={() => removeSymbolFromDashboard(chart.symbol)}>حذف</button>
                        </div>
                        <ResponsiveContainer width="100%" height="74%">
                          <AreaChart data={dataInRange}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="date" stroke="#94a3b8" hide />
                            <YAxis stroke="#94a3b8" width={44} tickFormatter={formatCompactNumber} />
                            <Tooltip formatter={(value) => formatPreciseNumber(value)} />
                            <Area dataKey="value" stroke="#38bdf8" fill="#38bdf833" />
                            <Line type="monotone" dataKey="value" stroke="#22d3ee" dot={false} strokeWidth={1.7} />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-4">
              <h3 className="font-semibold flex items-center gap-2"><WandSparkles size={16} /> سلامت فید جهانی</h3>
              <ul className="text-sm text-slate-300 space-y-1 mt-2">
                <li>سالم: {freshness?.totals?.healthy ?? '-'}</li>
                <li>نزدیک سررسید: {freshness?.totals?.due_soon ?? '-'}</li>
                <li>دیرهنگام: {freshness?.totals?.stale ?? '-'}</li>
                <li>بدون آپدیت: {freshness?.totals?.never_updated ?? '-'}</li>
              </ul>
            </div>
          </section>
        )}

        {activeTab === 'manage' && (
          <section className="bg-slate-900/80 border border-slate-700 rounded-xl p-4 space-y-4">
            <div className="grid md:grid-cols-7 gap-3">
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><Search size={16} /><input value={search} onChange={(e) => { setSearch(e.target.value); setSymbolsPage(1) }} placeholder="جستجو" className="bg-transparent w-full outline-none" /></label>
              <select value={sourceFilter} onChange={(e) => { setSourceFilter(e.target.value); setSymbolsPage(1) }} className="bg-slate-950 rounded-lg px-3 py-2"><option value="">همه منابع</option>{availableSources.map((s) => <option key={s} value={s}>{s}</option>)}</select>
              <input value={dbnomicsProviderSearch} onChange={(e) => setDbnomicsProviderSearch(e.target.value)} placeholder="جستجو زیرمنبع DBNOMICS" disabled={sourceFilter !== 'DBNOMICS'} className="bg-slate-950 rounded-lg px-3 py-2 disabled:opacity-50" />
              <select value={dbnomicsProviderFilter} onChange={(e) => { setDbnomicsProviderFilter(e.target.value); setSymbolsPage(1) }} disabled={sourceFilter !== 'DBNOMICS'} className="bg-slate-950 rounded-lg px-3 py-2 disabled:opacity-50">
                <option value="">زیرمنبع DBNOMICS</option>
                {dbnomicsProviders.map((item) => <option key={item.provider} value={item.provider}>{item.provider} ({item.indicators})</option>)}
              </select>
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><SlidersHorizontal size={16} /><input type="checkbox" checked={withDataOnly} onChange={(e) => { setWithDataOnly(e.target.checked); setSymbolsPage(1) }} /> فقط دارای دیتا</label>
              <select value={symbolsPageSize} onChange={(e) => { setSymbolsPageSize(Number(e.target.value)); setSymbolsPage(1) }} className="bg-slate-950 rounded-lg px-3 py-2"><option value={50}>۵۰</option><option value={100}>۱۰۰</option><option value={200}>۲۰۰</option><option value={500}>۵۰۰</option></select>
              <button className="bg-cyan-700 rounded-lg px-3 py-2" onClick={loadDashboard}>اعمال فیلتر</button>
            </div>

            {sourceFilter === 'DBNOMICS' && <div className="text-xs text-slate-400">برای زیرمنبع‌های خیلی زیاد، ابتدا در فیلد جستجو یک بخش از نام زیرمنبع را وارد کن.</div>}

            <div className="overflow-auto max-h-[560px]">
              <table className="w-full text-sm">
                <thead className="text-slate-400"><tr><th className="text-right p-2">نماد</th><th className="text-right p-2">نام</th><th className="text-right p-2">منبع</th><th className="text-right p-2">زیرمنبع</th><th className="text-right p-2">آپدیت خودکار</th><th className="text-right p-2">عملیات</th></tr></thead>
                <tbody>
                  {symbols.map((row) => (
                    <tr key={row.id} className="border-t border-slate-800">
                      <td className="p-2">{row.symbol}</td>
                      <td className="p-2">{row.name}</td>
                      <td className="p-2">{row.source}</td>
                      <td className="p-2">{row.dbnomics_provider || '-'}</td>
                      <td className="p-2"><input defaultValue={row.update_interval_days} type="number" min="1" className="w-20 bg-slate-950 rounded px-2 py-1" onBlur={(e) => changeInterval(row.symbol, e.target.value)} /> روز</td>
                      <td className="p-2 flex flex-wrap gap-2">
                        <button onClick={() => openExpandedChart(row.symbol)} className="px-2 py-1 bg-slate-800 rounded">نمایش</button>
                        <button disabled={!sourceSupportsManualRefresh(row.source)} onClick={() => refreshNow(row.symbol)} className="px-2 py-1 bg-emerald-700 disabled:bg-slate-700 rounded">دریافت فوری</button>
                        <button onClick={() => addSymbolToDashboard(row.symbol)} className="px-2 py-1 bg-indigo-700 rounded">افزودن</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-400">تعداد کل شاخص‌ها: {symbolsTotal}</span>
              <div className="flex items-center gap-2">
                <button disabled={symbolsPage <= 1} onClick={() => setSymbolsPage((p) => Math.max(1, p - 1))} className="px-2 py-1 bg-slate-800 rounded disabled:opacity-40">قبلی</button>
                <span>{symbolsPage} / {symbolsTotalPages}</span>
                <button disabled={symbolsPage >= symbolsTotalPages} onClick={() => setSymbolsPage((p) => Math.min(symbolsTotalPages, p + 1))} className="px-2 py-1 bg-slate-800 rounded disabled:opacity-40">بعدی</button>
              </div>
            </div>

            {!loading && symbols.length === 0 && <div className="text-sm text-amber-300">هیچ نمادی پیدا نشد.</div>}
            {loading && <div className="text-sm text-slate-400">در حال دریافت لیست...</div>}
          </section>
        )}

        {activeTab === 'users' && (
          <section className="grid lg:grid-cols-2 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
              <h3 className="font-semibold flex items-center gap-2"><UserPlus size={16} /> افزودن کاربر جدید</h3>
              <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="username" className="w-full bg-slate-950 rounded px-3 py-2" />
              <input value={newDisplayName} onChange={(e) => setNewDisplayName(e.target.value)} placeholder="نام نمایشی" className="w-full bg-slate-950 rounded px-3 py-2" />
              <button className="px-3 py-2 bg-cyan-700 rounded" onClick={addUser}>ساخت کاربر</button>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
              <h3 className="font-semibold">داشبورد اختصاصی من</h3>
              <div className="text-xs text-slate-400">نمادهای پیش‌فرض (حداکثر ۱۲):</div>
              <div className="flex gap-2 flex-wrap">{defaultDashboardSymbols.map((s) => <button key={s} onClick={() => removeSymbolFromDashboard(s)} className="px-2 py-1 rounded bg-slate-800 text-xs">{s} ✕</button>)}</div>
            </div>
          </section>
        )}

        {activeTab === 'lab' && (
          <section className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
            <h2 className="font-semibold flex items-center gap-2"><FlaskConical size={18} /> آزمایشگاه ترکیب شاخص‌ها</h2>
            <div className="grid md:grid-cols-3 gap-3">
              {variables.map((v, idx) => (
                <div key={v.id} className="bg-slate-950 rounded-lg p-2 space-y-2">
                  <div className="text-xs text-slate-400">متغیر {v.id}</div>
                  <select value={v.symbol} onChange={(e) => setVariables((prev) => prev.map((item) => item.id === v.id ? { ...item, symbol: e.target.value } : item))} className="w-full bg-slate-900 rounded px-2 py-2">
                    <option value="">انتخاب نماد</option>
                    {symbols.filter((s) => s.has_data).map((s) => <option key={`${v.id}-${s.id}`} value={s.symbol}>{s.symbol}</option>)}
                  </select>
                  {idx > 1 && <button onClick={() => setVariables((prev) => prev.filter((item) => item.id !== v.id))} className="text-xs text-red-400">حذف</button>}
                </div>
                <ResponsiveContainer width="100%" height="88%"><ComposedChart data={selectedRangeData}><CartesianGrid strokeDasharray="3 3" stroke="#334155" /><XAxis dataKey="date" stroke="#94a3b8" minTickGap={30} /><YAxis stroke="#94a3b8" tickFormatter={formatCompactNumber} width={72} /><Tooltip formatter={(value) => formatPreciseNumber(value)} /><Legend />{chartAverage !== null && <ReferenceLine y={chartAverage} label="میانگین" stroke="#f59e0b" strokeDasharray="4 4" />}<Area name="حجم کلی" dataKey="value" stroke="#22d3ee" fill="#22d3ee33" /><Line name="روند دقیق" type="monotone" dataKey="value" stroke="#06b6d4" dot={false} strokeWidth={2} /><Brush dataKey="date" height={20} stroke="#06b6d4" travellerWidth={8} /></ComposedChart></ResponsiveContainer>
              </>}
            </div>
            <button className="px-3 py-1 bg-slate-800 rounded" onClick={() => setVariables((prev) => [...prev, { id: String.fromCharCode(65 + prev.length), symbol: '' }])}>افزودن متغیر</button>
            <div className="flex gap-2">
              <input value={formula} onChange={(e) => setFormula(e.target.value)} className="flex-1 bg-slate-950 rounded-lg px-3 py-2 font-mono" />
              <button className="px-4 py-2 bg-purple-700 rounded-lg" onClick={runFormula}>اجرا</button>
            </div>
            <div className="h-[360px] bg-slate-950 rounded-lg p-3">
              {labData.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-400">نتیجه اینجا نمایش داده می‌شود.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={labData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip />
                    <Area dataKey="value" stroke="#c084fc" fill="#c084fc33" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>
        )}
      </div>

      {expandedChartOpen && (
        <div className="fixed inset-0 bg-slate-950/90 z-50 p-6">
          <div className="max-w-7xl mx-auto h-full bg-slate-900 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">نمای بزرگ نمودار {expandedChartSymbol}</h3>
              <div className="flex items-center gap-2">
                {CHART_RANGES.map((range) => (
                  <button key={range.key} onClick={() => setExpandedChartRange(range.key)} className={`px-2 py-1 rounded text-xs ${expandedChartRange === range.key ? 'bg-cyan-700' : 'bg-slate-800'}`}>{range.label}</button>
                ))}
                <button className="px-3 py-1 rounded bg-rose-700" onClick={() => setExpandedChartOpen(false)}><Minimize2 size={14} /></button>
              </div>
            </div>
            <div className="text-sm mb-2 text-cyan-300">
              {expandedRangeData.length ? `آخرین مقدار: ${formatPreciseNumber(expandedRangeData[expandedRangeData.length - 1].value)}` : 'بدون داده'}
            </div>
            <div className="h-[84%]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={expandedRangeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" tickFormatter={formatCompactNumber} />
                  <Tooltip formatter={(value) => formatPreciseNumber(value)} />
                  <Legend />
                  {expandedAverage !== null && <ReferenceLine y={expandedAverage} label="میانگین" stroke="#f59e0b" strokeDasharray="4 4" />}
                  <Area dataKey="value" stroke="#22d3ee" fill="#22d3ee33" />
                  <Line type="monotone" dataKey="value" stroke="#06b6d4" dot={false} strokeWidth={2} />
                  <Brush dataKey="date" height={24} stroke="#06b6d4" travellerWidth={10} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function LoginView({ users, loginUserId, setLoginUserId, login, newUsername, setNewUsername, newDisplayName, setNewDisplayName, addUser, backendConnected, message }) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 flex items-center" dir="rtl">
      <div className="max-w-5xl w-full mx-auto grid lg:grid-cols-2 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-xl font-bold flex items-center gap-2"><Users size={18} /> ورود به داشبورد شخصی</h2>
          <p className={`text-xs ${backendConnected === false ? 'text-rose-400' : 'text-emerald-400'}`}>{backendConnected === false ? 'ارتباط با API قطع است' : 'بک‌اند در دسترس است'}</p>
          <select value={loginUserId} onChange={(e) => setLoginUserId(e.target.value)} className="w-full bg-slate-950 rounded px-3 py-2">
            <option value="">انتخاب کاربر</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.display_name} ({u.username})</option>)}
          </select>
          <button onClick={login} className="w-full bg-cyan-700 rounded px-3 py-2">ورود</button>
          {message && <div className="text-sm text-slate-300">{message}</div>}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-3">
          <h3 className="font-semibold flex items-center gap-2"><UserPlus size={16} /> ساخت حساب جدید</h3>
          <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="username" className="w-full bg-slate-950 rounded px-3 py-2" />
          <input value={newDisplayName} onChange={(e) => setNewDisplayName(e.target.value)} placeholder="نام نمایشی" className="w-full bg-slate-950 rounded px-3 py-2" />
          <button className="w-full bg-emerald-700 rounded px-3 py-2" onClick={addUser}>ایجاد کاربر</button>
        </div>
      </div>
    </div>
  )
}

function StatCard({ title, value }) {
  return (
    <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-4">
      <div className="text-sm text-slate-400">{title}</div>
      <div className="text-2xl font-bold mt-2">{value ?? '-'}</div>
    </div>
  )
}
