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
import { Activity, FlaskConical, LogOut, RefreshCcw, Search, SlidersHorizontal, UserPlus, Users, WandSparkles } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

const ACTIVE_USER_STORAGE_KEY = 'economy_active_user_id'

const extractErrorMessage = (err, fallback) => {
  if (err?.response?.data?.detail) return err.response.data.detail
  if (err?.message) return err.message
  return fallback
}

const sourceSupportsManualRefresh = (source) => ['FRED', 'YAHOO', 'WORLDBANK', 'ECB', 'DBNOMICS'].includes(source)
const formatCompactNumber = (value) => Intl.NumberFormat('fa-IR', { notation: 'compact', maximumFractionDigits: 2 }).format(value || 0)
const formatPreciseNumber = (value) => Intl.NumberFormat('fa-IR', { maximumFractionDigits: 4 }).format(value || 0)

export default function App() {
  const [summary, setSummary] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [activeTab, setActiveTab] = useState('dashboard')
  const [sourceFilter, setSourceFilter] = useState('')
  const [dbnomicsProviderFilter, setDbnomicsProviderFilter] = useState('')
  const [dbnomicsProviders, setDbnomicsProviders] = useState([])
  const [search, setSearch] = useState('')
  const [withDataOnly, setWithDataOnly] = useState(false)

  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [loginUserId, setLoginUserId] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [defaultDashboardSymbols, setDefaultDashboardSymbols] = useState([])

  const [selectedSymbol, setSelectedSymbol] = useState('')
  const [chartData, setChartData] = useState([])
  const [dashboardCharts, setDashboardCharts] = useState([])
  const [chartLoading, setChartLoading] = useState(false)

  const [variables, setVariables] = useState([{ id: 'A', symbol: '' }, { id: 'B', symbol: '' }])
  const [formula, setFormula] = useState('(A / B) * 100')
  const [labData, setLabData] = useState([])
  const [backendConnected, setBackendConnected] = useState(null)


  const activeUser = useMemo(() => users.find((u) => String(u.id) === String(selectedUserId)) || null, [users, selectedUserId])
  const isLoggedIn = !!activeUser

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
      setLoginUserId(String(allUsers[0].id))
      // افزودن کاربر اول به عنوان انتخاب شده در صورت لاگین نبودن
      if (!selectedUserId) setSelectedUserId(String(allUsers[0].id))
    }
  }, [loginUserId, selectedUserId])

  const loadDbnomicsProviders = useCallback(async () => {
    try {
      const params = withDataOnly ? { with_data_only: true } : {}
      const res = await axios.get(`${API_BASE}/data/dbnomics/providers`, { params })
      setDbnomicsProviders(res.data || [])
    } catch {
      setDbnomicsProviders([])
    }
  }, [withDataOnly])

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: 1000 }
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
      setSymbols(symbolsRes.data)
      setBackendConnected(true)
      setMessage('')
    } catch (err) {
      setBackendConnected(false)
      setSummary(null)
      setFreshness(null)
      setSymbols([])
      setMessage(extractErrorMessage(err, 'خطا در بارگذاری داشبورد. ارتباط فرانت با بک‌اند برقرار نیست یا API در دسترس نیست.'))
    } finally {
      setLoading(false)
    }
  }, [dbnomicsProviderFilter, search, sourceFilter, withDataOnly])

  const loadUserDashboard = useCallback(async (userId) => {
    if (!userId) return
    try {
      const res = await axios.get(`${API_BASE}/users/${userId}/dashboard`)
      const symbolsFromUser = res.data?.symbols || []
      setDefaultDashboardSymbols(symbolsFromUser)
      if (!selectedSymbol && symbolsFromUser.length) setSelectedSymbol(symbolsFromUser[0])

      const chartPromises = symbolsFromUser.slice(0, 12).map(async (sym) => {
        try {
          const chartRes = await axios.get(`${API_BASE}/data/${sym}`)
          return { symbol: sym, data: chartRes.data?.data || [] }
        } catch {
          return { symbol: sym, data: [] }
        }
      })
      setDashboardCharts(await Promise.all(chartPromises))
    } catch {
      setDefaultDashboardSymbols([])
      setDashboardCharts([])
    }
  }, [selectedSymbol])

  useEffect(() => {
    Promise.all([loadUsers(), loadDashboard()]).catch(() => null)
  }, [loadDashboard, loadUsers])

  useEffect(() => {
    if (sourceFilter === 'DBNOMICS') {
      loadDbnomicsProviders().catch(() => null)
    } else {
      setDbnomicsProviderFilter('')
    }
  }, [loadDbnomicsProviders, sourceFilter])

  useEffect(() => {
    if (selectedUserId) loadUserDashboard(selectedUserId)
  }, [loadUserDashboard, selectedUserId])

  const persistDashboardSymbols = useCallback(async (nextSymbols, successMessage) => {
    if (!selectedUserId) {
      setMessage('ابتدا وارد حساب کاربری خودت شو.')
      return
    }

    try {
      await axios.put(`${API_BASE}/users/${selectedUserId}/dashboard`, { symbols: nextSymbols })
      setDefaultDashboardSymbols(nextSymbols)
      await loadUserDashboard(selectedUserId)
      if (successMessage) setMessage(successMessage)
    } catch (err) {
      setMessage(extractErrorMessage(err, 'ذخیره داشبورد ناموفق بود.'))
    }
  }, [loadUserDashboard, selectedUserId])

  useEffect(() => {
    if (!selectedSymbol) return
    setChartLoading(true)
    axios
      .get(`${API_BASE}/data/${selectedSymbol}`)
      .then((res) => setChartData(res.data.data || []))
      .catch(() => setChartData([]))
      .finally(() => setChartLoading(false))
  }, [selectedSymbol])

  const availableSources = useMemo(() => (summary?.sources || []).map((s) => s.source), [summary])

  const runPipeline = async (path, successMessage) => {
    try {
      await axios.post(`${API_BASE}${path}`)
      setMessage(successMessage)
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
      setMessage(`دستور دریافت فوری برای ${symbol} ارسال شد.`)
      await loadDashboard()
      if (selectedUserId) await loadUserDashboard(selectedUserId)
    } catch (err) {
      setMessage(extractErrorMessage(err, 'رفرش فوری برای این منبع پشتیبانی نمی‌شود.'))
    }
  }

  const addUser = async () => {
    try {
      const res = await axios.post(`${API_BASE}/users`, { username: newUsername, display_name: newDisplayName })
      setNewUsername('')
      setNewDisplayName('')
      await loadUsers()
      const createdUserId = String(res.data?.id || '')
      if (createdUserId) {
        setLoginUserId(createdUserId)
      }
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

  const saveDefaultDashboard = async () => {
    await persistDashboardSymbols(defaultDashboardSymbols, 'داشبورد پیش‌فرض کاربر ذخیره شد.')
  }

  const addSymbolToDashboard = async (symbol) => {
    if (defaultDashboardSymbols.includes(symbol)) return
    if (defaultDashboardSymbols.length >= 12) return setMessage('حداکثر ۱۲ نماد می‌توانی برای داشبورد انتخاب کنی.')

    const nextSymbols = [...defaultDashboardSymbols, symbol]
    await persistDashboardSymbols(nextSymbols, `${symbol} به داشبوردت اضافه شد.`)
  }

  const removeSymbolFromDashboard = async (symbol) => {
    const nextSymbols = defaultDashboardSymbols.filter((item) => item !== symbol)
    await persistDashboardSymbols(nextSymbols, `${symbol} از داشبورد حذف شد.`)
  }

  const chartAverage = useMemo(() => {
    if (!chartData.length) return null
    const valid = chartData.map((item) => Number(item.value)).filter((val) => Number.isFinite(val))
    if (!valid.length) return null
    return valid.reduce((sum, val) => sum + val, 0) / valid.length
  }, [chartData])

  const runFormula = async () => {
    const variablesPayload = {}
    for (const v of variables) {
      if (!v.symbol) return setMessage('برای همه متغیرها نماد انتخاب کن.')
      variablesPayload[v.id] = v.symbol
    }

    try {
      const res = await axios.post(`${API_BASE}/data/lab/formula`, { formula, variables: variablesPayload })
      setLabData(res.data || [])
      if (!res.data?.length) setMessage('داده مشترک برای این ترکیب پیدا نشد.')
    } catch (err) {
      setMessage(extractErrorMessage(err, 'فرمول معتبر نیست یا دیتای کافی وجود ندارد.'))
    }
  }

  if (!isLoggedIn) {
    return (
      <LoginView
        users={users}
        loginUserId={loginUserId}
        setLoginUserId={setLoginUserId}
        login={login}
        newUsername={newUsername}
        setNewUsername={setNewUsername}
        newDisplayName={newDisplayName}
        setNewDisplayName={setNewDisplayName}
        addUser={addUser}
        backendConnected={backendConnected}
        message={message}
      />
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6" dir="rtl">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2"><Activity className="text-cyan-400" /> پنل اقتصاد جهانی</h1>
            <p className="text-slate-400 text-sm">کاربر: <span className="text-cyan-300">{activeUser?.display_name}</span> ({activeUser?.username})</p>
            <p className="text-slate-400 text-sm">چندکاربره + داشبورد شخصی + فیلتر DBNOMICS + آزمایشگاه</p>
            <p className={`text-xs mt-1 ${backendConnected === false ? 'text-rose-400' : 'text-emerald-400'}`}>
              {backendConnected === false ? 'ارتباط با بک‌اند قطع است' : backendConnected === true ? `اتصال API برقرار است (${API_BASE})` : 'وضعیت اتصال در حال بررسی...'}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button className="px-4 py-2 bg-slate-800 rounded-lg" onClick={loadDashboard}><RefreshCcw size={16} className="inline ml-1" /> رفرش</button>
            <button className="px-4 py-2 bg-cyan-700 rounded-lg" onClick={() => runPipeline('/pipeline/trigger-all', 'دریافت موازی داده‌ها شروع شد.')}>دریافت سریع</button>
            <button className="px-4 py-2 bg-fuchsia-700 rounded-lg" onClick={() => runPipeline('/discover/dbnomics', 'کاوش بانک‌های مرکزی DBNOMICS آغاز شد.')}>کاوش بانک‌های مرکزی</button>
            <button className="px-4 py-2 bg-rose-700 rounded-lg" onClick={logout}><LogOut size={16} className="inline ml-1" /> خروج</button>
          </div>
        </header>

        {message && <div className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm">{message}</div>}

        <div className="flex gap-2">
          {[
            ['dashboard', 'داشبورد من'],
            ['manage', 'مدیریت شاخص‌ها'],
            ['users', 'تنظیمات حساب'],
            ['lab', 'آزمایشگاه']
          ].map(([key, label]) => (
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

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2"><Users size={16} /> داشبورد پیش‌فرض من</h3>
              {dashboardCharts.length === 0 ? <div className="text-slate-400 text-sm">برای حساب شما هنوز نمودار پیش‌فرض تنظیم نشده.</div> : (
                <div className="grid lg:grid-cols-2 gap-4">
                  {dashboardCharts.map((c) => (
                    <div key={c.symbol} className="h-[240px] bg-slate-950 rounded-lg p-2">
                      <div className="text-xs text-slate-300 mb-1 flex items-center justify-between">
                        <span>{c.symbol}</span>
                        <span className="text-slate-400">{c.data.length ? formatCompactNumber(c.data.at(-1)?.value) : 'بدون داده'}</span>
                      </div>
                      <ResponsiveContainer width="100%" height="90%">
                        <AreaChart data={c.data}>
                          <defs>
                            <linearGradient id={`mini-${c.symbol}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="10%" stopColor="#38bdf8" stopOpacity={0.4} />
                              <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                          <XAxis dataKey="date" stroke="#94a3b8" hide />
                          <YAxis stroke="#94a3b8" width={42} tickFormatter={formatCompactNumber} />
                          <Tooltip formatter={(value) => formatPreciseNumber(value)} />
                          <Area dataKey="value" stroke="#38bdf8" fill={`url(#mini-${c.symbol})`} />
                          <Line type="monotone" dataKey="value" stroke="#22d3ee" dot={false} strokeWidth={1.7} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="grid lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-4 h-[360px]">
                {!selectedSymbol ? (
                  <div className="h-full flex items-center justify-center text-slate-400">از تب مدیریت یک نماد انتخاب کن تا نمودارش اینجا نمایش داده شود.</div>
                ) : chartLoading ? (
                  <div className="h-full flex items-center justify-center text-slate-400">در حال دریافت نمودار...</div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData}>
                      <defs><linearGradient id="v" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22d3ee" stopOpacity={0.6} /><stop offset="95%" stopColor="#22d3ee" stopOpacity={0} /></linearGradient></defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" stroke="#94a3b8" minTickGap={32} />
                      <YAxis stroke="#94a3b8" tickFormatter={formatCompactNumber} width={72} />
                      <Tooltip formatter={(value) => formatPreciseNumber(value)} />
                      <Legend />
                      {chartAverage !== null && <ReferenceLine y={chartAverage} label="میانگین" stroke="#f59e0b" strokeDasharray="4 4" />}
                      <Area name="حجم کلی" dataKey="value" stroke="#22d3ee" fill="url(#v)" />
                      <Line name="روند دقیق" type="monotone" dataKey="value" stroke="#06b6d4" dot={false} strokeWidth={2} />
                      <Brush dataKey="date" height={20} stroke="#06b6d4" travellerWidth={8} />
                    </ComposedChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                <h3 className="font-semibold flex items-center gap-2"><WandSparkles size={16} /> سلامت فید جهانی</h3>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>سالم: {freshness?.totals?.healthy ?? '-'}</li>
                  <li>نزدیک سررسید: {freshness?.totals?.due_soon ?? '-'}</li>
                  <li>دیرهنگام: {freshness?.totals?.stale ?? '-'}</li>
                  <li>بدون آپدیت: {freshness?.totals?.never_updated ?? '-'}</li>
                </ul>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'manage' && (
          <section className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
            <div className="grid md:grid-cols-5 gap-3">
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو" className="bg-transparent w-full outline-none" /></label>
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="bg-slate-950 rounded-lg px-3 py-2">
                <option value="">همه منابع</option>
                {availableSources.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select
                value={dbnomicsProviderFilter}
                onChange={(e) => setDbnomicsProviderFilter(e.target.value)}
                disabled={sourceFilter !== 'DBNOMICS'}
                className="bg-slate-950 rounded-lg px-3 py-2 disabled:opacity-50"
              >
                <option value="">زیرمنبع DBNOMICS</option>
                {dbnomicsProviders.map((item) => <option key={item.provider} value={item.provider}>{item.provider} ({item.indicators})</option>)}
              </select>
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><SlidersHorizontal size={16} />
                <input type="checkbox" checked={withDataOnly} onChange={(e) => setWithDataOnly(e.target.checked)} /> فقط دارای دیتا
              </label>
              <button className="bg-cyan-700 rounded-lg px-3 py-2" onClick={loadDashboard}>اعمال فیلتر</button>
            </div>

            {sourceFilter === 'DBNOMICS' && (
              <div className="text-xs text-slate-400">زیرمنبع‌ها به‌صورت پویا از بک‌اند خوانده می‌شوند. اگر تازه کاوش کردی، یک بار «رفرش» بزن.</div>
            )}

            <div className="overflow-auto max-h-[520px]">
              <table className="w-full text-sm">
                <thead className="text-slate-400"><tr><th className="text-right p-2">نماد</th><th className="text-right p-2">نام</th><th className="text-right p-2">منبع</th><th className="text-right p-2">زیرمنبع</th><th className="text-right p-2">آپدیت خودکار</th><th className="text-right p-2">عملیات</th></tr></thead>
                <tbody>
                  {symbols.map((row) => (
                    <tr key={row.id} className="border-t border-slate-800">
                      <td className="p-2">{row.symbol}</td>
                      <td className="p-2">{row.name}</td>
                      <td className="p-2">{row.source}</td>
                      <td className="p-2">{row.dbnomics_provider || '-'}</td>
                      <td className="p-2">
                        <input defaultValue={row.update_interval_days} type="number" min="1" className="w-20 bg-slate-950 rounded px-2 py-1" onBlur={(e) => changeInterval(row.symbol, e.target.value)} /> روز
                      </td>
                      <td className="p-2 flex flex-wrap gap-2">
                        <button onClick={() => setSelectedSymbol(row.symbol)} className="px-2 py-1 bg-slate-800 rounded">نمایش</button>
                        <button disabled={!sourceSupportsManualRefresh(row.source)} onClick={() => refreshNow(row.symbol)} className="px-2 py-1 bg-emerald-700 disabled:bg-slate-700 rounded">دریافت فوری</button>
                        <button onClick={() => addSymbolToDashboard(row.symbol)} className="px-2 py-1 bg-indigo-700 rounded">افزودن به داشبورد من</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!loading && symbols.length === 0 && <div className="text-sm text-amber-300">هیچ نمادی پیدا نشد. فیلترها را کم کن یا گزینه «فقط دارای دیتا» را خاموش کن.</div>}
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
              <button className="px-3 py-2 bg-emerald-700 rounded" onClick={saveDefaultDashboard}>ذخیره داشبورد من</button>
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
              ))}
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
    </div>
  )
}

function LoginView({
  users,
  loginUserId,
  setLoginUserId,
  login,
  newUsername,
  setNewUsername,
  newDisplayName,
  setNewDisplayName,
  addUser,
  backendConnected,
  message
}) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 flex items-center" dir="rtl">
      <div className="max-w-5xl w-full mx-auto grid lg:grid-cols-2 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-xl font-bold flex items-center gap-2"><Users size={18} /> ورود به داشبورد شخصی</h2>
          <p className={`text-xs ${backendConnected === false ? 'text-rose-400' : 'text-emerald-400'}`}>
            {backendConnected === false ? 'ارتباط با API قطع است' : 'بک‌اند در دسترس است'}
          </p>
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
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="text-sm text-slate-400">{title}</div>
      <div className="text-2xl font-bold mt-2">{value ?? '-'}</div>
    </div>
  )
}
