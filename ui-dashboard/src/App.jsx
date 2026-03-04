import { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { Activity, FlaskConical, RefreshCcw, Search, SlidersHorizontal, UserPlus, Users, WandSparkles } from 'lucide-react'

const API_BASE = 'http://localhost:8000/api'

const sourceSupportsManualRefresh = (source) => ['FRED', 'YAHOO', 'WORLDBANK', 'ECB', 'DBNOMICS'].includes(source)

import { Activity, FlaskConical, RefreshCcw, Search, SlidersHorizontal, WandSparkles } from 'lucide-react'

const API_BASE = 'http://localhost:8000/api'

const sourceSupportsManualRefresh = (source) => ['FRED', 'YAHOO', 'WORLDBANK', 'ECB'].includes(source)


export default function App() {
  const [summary, setSummary] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const [activeTab, setActiveTab] = useState('dashboard')
  const [sourceFilter, setSourceFilter] = useState('')
  const [dbnomicsProviderFilter, setDbnomicsProviderFilter] = useState('')
  const [search, setSearch] = useState('')
  const [withDataOnly, setWithDataOnly] = useState(true)

  const [users, setUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState('')
  const [newUsername, setNewUsername] = useState('')
  const [newDisplayName, setNewDisplayName] = useState('')
  const [defaultDashboardSymbols, setDefaultDashboardSymbols] = useState([])

  const [selectedSymbol, setSelectedSymbol] = useState('')
  const [singleChartData, setSingleChartData] = useState([])
  const [dashboardCharts, setDashboardCharts] = useState([])

  const [search, setSearch] = useState('')
  const [withDataOnly, setWithDataOnly] = useState(true)

  const [selectedSymbol, setSelectedSymbol] = useState('')
  const [chartData, setChartData] = useState([])

  const [chartLoading, setChartLoading] = useState(false)

  const [variables, setVariables] = useState([{ id: 'A', symbol: '' }, { id: 'B', symbol: '' }])
  const [formula, setFormula] = useState('(A / B) * 100')
  const [labData, setLabData] = useState([])


  const loadUsers = async () => {
    const res = await axios.get(`${API_BASE}/users`)
    setUsers(res.data || [])
    if (!selectedUserId && res.data?.length) setSelectedUserId(String(res.data[0].id))
  }

  const loadDashboard = async () => {
    setLoading(true)
    try {
      const params = { limit: 1000 }
      if (sourceFilter) params.source = sourceFilter

      if (dbnomicsProviderFilter) params.dbnomics_provider = dbnomicsProviderFilter


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
      setMessage('')

    } catch {

    } catch (err) {

      setMessage('خطا در بارگذاری داشبورد. بک‌اند را بررسی کن.')
    } finally {
      setLoading(false)
    }
  }


  const loadUserDashboard = async (userId) => {
    if (!userId) return
    try {
      const res = await axios.get(`${API_BASE}/users/${userId}/dashboard`)
      const symbolsFromUser = res.data?.symbols || []
      setDefaultDashboardSymbols(symbolsFromUser)
      if (!selectedSymbol && symbolsFromUser.length) setSelectedSymbol(symbolsFromUser[0])

      const chartPromises = symbolsFromUser.slice(0, 6).map(async (sym) => {
        const chartRes = await axios.get(`${API_BASE}/data/${sym}`)
        return { symbol: sym, data: chartRes.data?.data || [] }
      })
      setDashboardCharts(await Promise.all(chartPromises))
    } catch {
      setDefaultDashboardSymbols([])
      setDashboardCharts([])
    }
  }

  useEffect(() => {
    Promise.all([loadUsers(), loadDashboard()]).catch(() => null)
  }, [])

  useEffect(() => {
    if (selectedUserId) loadUserDashboard(selectedUserId)
  }, [selectedUserId])

  useEffect(() => {

  useEffect(() => {
    loadDashboard()
  }, [])

  useEffect(() => {
    if (!selectedSymbol) return
    setChartLoading(true)
    axios
      .get(`${API_BASE}/data/${selectedSymbol}`)

      .then((res) => setSingleChartData(res.data.data || []))
      .catch(() => setSingleChartData([]))
      .finally(() => setChartLoading(false))
  }, [selectedSymbol])

  const availableSources = useMemo(() => (summary?.sources || []).map((s) => s.source), [summary])
  const dbnomicsProviders = useMemo(() => [...new Set(symbols.filter((s) => s.source === 'DBNOMICS' && s.dbnomics_provider).map((s) => s.dbnomics_provider))], [symbols])

      .then((res) => setChartData(res.data.data || []))
      .catch(() => setChartData([]))
      .finally(() => setChartLoading(false))
  }, [selectedSymbol])

  const availableSources = useMemo(() => {
    if (!summary?.sources) return []
    return summary.sources.map((s) => s.source)
  }, [summary])


  const runPipeline = async (path, successMessage) => {
    try {
      await axios.post(`${API_BASE}${path}`)
      setMessage(successMessage)
    } catch {
      setMessage('ارسال دستور انجام نشد.')
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
      setMessage(err?.response?.data?.detail || 'رفرش فوری برای این منبع پشتیبانی نمی‌شود.')
    }
  }


  const addUser = async () => {
    try {
      await axios.post(`${API_BASE}/users`, { username: newUsername, display_name: newDisplayName })
      setNewUsername('')
      setNewDisplayName('')
      await loadUsers()
      setMessage('کاربر جدید ساخته شد.')
    } catch (err) {
      setMessage(err?.response?.data?.detail || 'ساخت کاربر ناموفق بود.')
    }
  }

  const saveDefaultDashboard = async () => {
    if (!selectedUserId) return setMessage('ابتدا یک کاربر انتخاب کن.')
    try {
      await axios.put(`${API_BASE}/users/${selectedUserId}/dashboard`, { symbols: defaultDashboardSymbols })
      setMessage('داشبورد پیش‌فرض کاربر ذخیره شد.')
      await loadUserDashboard(selectedUserId)
    } catch (err) {
      setMessage(err?.response?.data?.detail || 'ذخیره داشبورد ناموفق بود.')
    }
  }


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
    } catch {
      setMessage('فرمول معتبر نیست یا دیتای کافی وجود ندارد.')
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6" dir="rtl">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2"><Activity className="text-cyan-400" /> پنل اقتصاد جهانی</h1>

            <p className="text-slate-400 text-sm">چندکاربره + داشبورد شخصی + فیلتر DBNOMICS + آزمایشگاه</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button className="px-4 py-2 bg-slate-800 rounded-lg" onClick={loadDashboard}><RefreshCcw size={16} className="inline ml-1" /> رفرش</button>
            <button className="px-4 py-2 bg-cyan-700 rounded-lg" onClick={() => runPipeline('/pipeline/trigger-all', 'دریافت موازی داده‌ها شروع شد.')}>دریافت سریع</button>
            <button className="px-4 py-2 bg-amber-700 rounded-lg" onClick={() => runPipeline('/pipeline/massive-worldbank', 'ماشین شخم‌زن بانک جهانی روشن شد.')}>خزش گسترده WB</button>
            <button className="px-4 py-2 bg-fuchsia-700 rounded-lg" onClick={() => runPipeline('/discover/dbnomics', 'کاوش بانک‌های مرکزی DBNOMICS آغاز شد.')}>کاوش بانک‌های مرکزی</button>

            <p className="text-slate-400 text-sm">مدیریت شاخص‌ها، کنترل دریافت داده، آزمایشگاه ترکیب و پایش سلامت به‌روزرسانی</p>
          </div>
          <div className="flex gap-2">
            <button className="px-4 py-2 bg-slate-800 rounded-lg" onClick={loadDashboard}><RefreshCcw size={16} className="inline ml-1" /> رفرش</button>
            <button className="px-4 py-2 bg-cyan-700 rounded-lg" onClick={() => runPipeline('/pipeline/trigger-all', 'دریافت موازی داده‌ها شروع شد.')}>دریافت سریع</button>
            <button className="px-4 py-2 bg-amber-700 rounded-lg" onClick={() => runPipeline('/pipeline/massive-worldbank', 'ماشین شخم‌زن بانک جهانی روشن شد.')}>خزش گسترده WB</button>

          </div>
        </header>

        {message && <div className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm">{message}</div>}

        <div className="flex gap-2">
          {[
            ['dashboard', 'داشبورد'],
            ['manage', 'مدیریت شاخص‌ها'],

            ['users', 'کاربران'],

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
              <h3 className="font-semibold mb-3 flex items-center gap-2"><Users size={16} /> داشبورد پیش‌فرض کاربر</h3>
              {dashboardCharts.length === 0 ? <div className="text-slate-400 text-sm">برای کاربر انتخاب‌شده هنوز نمودار پیش‌فرض تنظیم نشده.</div> : (
                <div className="grid lg:grid-cols-2 gap-4">
                  {dashboardCharts.map((c) => (
                    <div key={c.symbol} className="h-[240px] bg-slate-950 rounded-lg p-2">
                      <div className="text-xs text-slate-300 mb-1">{c.symbol}</div>
                      <ResponsiveContainer width="100%" height="90%">
                        <AreaChart data={c.data}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                          <XAxis dataKey="date" stroke="#94a3b8" hide />
                          <YAxis stroke="#94a3b8" width={42} />
                          <Tooltip />
                          <Area dataKey="value" stroke="#22d3ee" fill="#22d3ee33" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ))}
                </div>
              )}
              <StatCard title="شاخص‌های دارای داده" value={summary?.totals?.indicators_with_data} />
              <StatCard title="کل رکوردها" value={summary?.totals?.economic_data_points} />
              <StatCard title="دیرهنگام" value={freshness?.totals?.stale} />
              <StatCard title="به‌زودی سررسید" value={freshness?.totals?.due_soon} />
            </div>
            <div className="grid lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-4 h-[360px]">

                {!selectedSymbol ? <div className="h-full flex items-center justify-center text-slate-400">از تب مدیریت یک نماد انتخاب کن.</div> : chartLoading ? <div className="h-full flex items-center justify-center text-slate-400">در حال دریافت نمودار...</div> : (
                  <ResponsiveContainer width="100%" height="100%"><AreaChart data={singleChartData}><CartesianGrid strokeDasharray="3 3" stroke="#334155" /><XAxis dataKey="date" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Area dataKey="value" stroke="#22d3ee" fill="#22d3ee33" /></AreaChart></ResponsiveContainer>
                )}
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                <h3 className="font-semibold flex items-center gap-2"><WandSparkles size={16} /> سلامت فید جهانی</h3>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>سالم: {freshness?.totals?.healthy ?? '-'}</li>
                  <li>نزدیک سررسید: {freshness?.totals?.due_soon ?? '-'}</li>
                  <li>دیرهنگام: {freshness?.totals?.stale ?? '-'}</li>

                {!selectedSymbol ? (
                  <div className="h-full flex items-center justify-center text-slate-400">از تب مدیریت یک نماد انتخاب کن تا نمودارش اینجا نمایش داده شود.</div>
                ) : chartLoading ? (
                  <div className="h-full flex items-center justify-center text-slate-400">در حال دریافت نمودار...</div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <defs><linearGradient id="v" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22d3ee" stopOpacity={0.6} /><stop offset="95%" stopColor="#22d3ee" stopOpacity={0} /></linearGradient></defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                      <XAxis dataKey="date" stroke="#94a3b8" />
                      <YAxis stroke="#94a3b8" />
                      <Tooltip />
                      <Area dataKey="value" stroke="#22d3ee" fill="url(#v)" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                <h3 className="font-semibold flex items-center gap-2"><WandSparkles size={16} /> ویژگی اضافه‌شده: سلامت فید جهانی</h3>
                <p className="text-sm text-slate-400">اینجا می‌بینی چند شاخص عقب افتاده، چندتا نزدیک به موعد آپدیت و چندتا هنوز هیچ‌وقت دریافت نشده‌اند.</p>
                <ul className="text-sm text-slate-300 space-y-1">
                  <li>سالم: {freshness?.totals?.healthy ?? '-'}</li>
                  <li>بدون آپدیت: {freshness?.totals?.never_updated ?? '-'}</li>
                  <li>تولید گزارش: {freshness?.generated_at || '-'}</li>

                </ul>
              </div>
            </div>
          </section>
        )}

        {activeTab === 'manage' && (
          <section className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">

            <div className="grid md:grid-cols-5 gap-3">
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو" className="bg-transparent w-full outline-none" /></label>
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="bg-slate-950 rounded-lg px-3 py-2"><option value="">همه منابع</option>{availableSources.map((s) => <option key={s} value={s}>{s}</option>)}</select>
              <select value={dbnomicsProviderFilter} onChange={(e) => setDbnomicsProviderFilter(e.target.value)} className="bg-slate-950 rounded-lg px-3 py-2"><option value="">زیرمنبع DBNOMICS</option>{dbnomicsProviders.map((s) => <option key={s} value={s}>{s}</option>)}</select>
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><SlidersHorizontal size={16} /><input type="checkbox" checked={withDataOnly} onChange={(e) => setWithDataOnly(e.target.checked)} /> فقط دارای دیتا</label>
              <button className="bg-cyan-700 rounded-lg px-3 py-2" onClick={loadDashboard}>اعمال فیلتر</button>
            </div>

            <div className="overflow-auto max-h-[520px]">
              <table className="w-full text-sm">
                <thead className="text-slate-400"><tr><th className="text-right p-2">نماد</th><th className="text-right p-2">نام</th><th className="text-right p-2">منبع</th><th className="text-right p-2">زیرمنبع</th><th className="text-right p-2">آپدیت خودکار</th><th className="text-right p-2">عملیات</th></tr></thead>
                <tbody>
                  {symbols.map((row) => (
                    <tr key={row.id} className="border-t border-slate-800">
                      <td className="p-2">{row.symbol}</td><td className="p-2">{row.name}</td><td className="p-2">{row.source}</td><td className="p-2">{row.dbnomics_provider || '-'}</td>
                      <td className="p-2"><input defaultValue={row.update_interval_days} type="number" min="1" className="w-20 bg-slate-950 rounded px-2 py-1" onBlur={(e) => changeInterval(row.symbol, e.target.value)} /> روز</td>
                      <td className="p-2 flex flex-wrap gap-2"><button onClick={() => setSelectedSymbol(row.symbol)} className="px-2 py-1 bg-slate-800 rounded">نمایش</button><button disabled={!sourceSupportsManualRefresh(row.source)} onClick={() => refreshNow(row.symbol)} className="px-2 py-1 bg-emerald-700 disabled:bg-slate-700 rounded">دریافت فوری</button>
                        <button onClick={() => setDefaultDashboardSymbols((prev) => prev.includes(row.symbol) ? prev : [...prev, row.symbol].slice(0, 12))} className="px-2 py-1 bg-indigo-700 rounded">افزودن به داشبورد کاربر</button></td>

            <div className="grid md:grid-cols-4 gap-3">
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو نام/نماد" className="bg-transparent w-full outline-none" /></label>
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="bg-slate-950 rounded-lg px-3 py-2">
                <option value="">همه منابع</option>
                {availableSources.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <label className="bg-slate-950 rounded-lg px-3 py-2 flex items-center gap-2"><SlidersHorizontal size={16} />
                <input type="checkbox" checked={withDataOnly} onChange={(e) => setWithDataOnly(e.target.checked)} /> فقط دارای دیتا
              </label>
              <button className="bg-cyan-700 rounded-lg px-3 py-2" onClick={loadDashboard}>اعمال فیلتر</button>
            </div>

            <div className="overflow-auto max-h-[500px]">
              <table className="w-full text-sm">
                <thead className="text-slate-400"><tr><th className="text-right p-2">نماد</th><th className="text-right p-2">نام</th><th className="text-right p-2">منبع</th><th className="text-right p-2">آپدیت خودکار</th><th className="text-right p-2">دکمه‌ها</th></tr></thead>
                <tbody>
                  {symbols.map((row) => (
                    <tr key={row.id} className="border-t border-slate-800">
                      <td className="p-2">{row.symbol}</td>
                      <td className="p-2">{row.name}</td>
                      <td className="p-2">{row.source}</td>
                      <td className="p-2">
                        <input
                          defaultValue={row.update_interval_days}
                          type="number"
                          min="1"
                          className="w-20 bg-slate-950 rounded px-2 py-1"
                          onBlur={(e) => changeInterval(row.symbol, e.target.value)}
                        /> روز
                      </td>
                      <td className="p-2 flex flex-wrap gap-2">
                        <button onClick={() => setSelectedSymbol(row.symbol)} className="px-2 py-1 bg-slate-800 rounded">نمایش</button>
                        <button disabled={!sourceSupportsManualRefresh(row.source)} onClick={() => refreshNow(row.symbol)} className="px-2 py-1 bg-emerald-700 disabled:bg-slate-700 rounded">دریافت فوری</button>
                      </td>

                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
              <h3 className="font-semibold">داشبورد اختصاصی کاربر</h3>
              <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} className="w-full bg-slate-950 rounded px-3 py-2">
                <option value="">انتخاب کاربر</option>
                {users.map((u) => <option key={u.id} value={u.id}>{u.display_name} ({u.username})</option>)}
              </select>
              <div className="text-xs text-slate-400">نمادهای پیش‌فرض (حداکثر ۱۲):</div>
              <div className="flex gap-2 flex-wrap">{defaultDashboardSymbols.map((s) => <button key={s} onClick={() => setDefaultDashboardSymbols((prev) => prev.filter((x) => x !== s))} className="px-2 py-1 rounded bg-slate-800 text-xs">{s} ✕</button>)}</div>
              <button className="px-3 py-2 bg-emerald-700 rounded" onClick={saveDefaultDashboard}>ذخیره داشبورد این کاربر</button>
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
            <div className="flex gap-2"><input value={formula} onChange={(e) => setFormula(e.target.value)} className="flex-1 bg-slate-950 rounded-lg px-3 py-2 font-mono" /><button className="px-4 py-2 bg-purple-700 rounded-lg" onClick={runFormula}>اجرا</button></div>
            <div className="h-[360px] bg-slate-950 rounded-lg p-3">{labData.length === 0 ? <div className="h-full flex items-center justify-center text-slate-400">نتیجه اینجا نمایش داده می‌شود.</div> : <ResponsiveContainer width="100%" height="100%"><AreaChart data={labData}><CartesianGrid strokeDasharray="3 3" stroke="#334155" /><XAxis dataKey="date" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip /><Area dataKey="value" stroke="#c084fc" fill="#c084fc33" /></AreaChart></ResponsiveContainer>}</div>

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

function StatCard({ title, value }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="text-sm text-slate-400">{title}</div>
      <div className="text-2xl font-bold mt-2">{value ?? '-'}</div>
    </div>
  )
}