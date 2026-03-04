import { useState, useEffect } from 'react';
import axios from 'axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FlaskConical, LineChart as ChartIcon, Activity, Plus, Trash2, Calculator } from 'lucide-react';

const API_BASE = "http://localhost:8000/api";

export default function App() {
  const [indicators, setIndicators] = useState([]);
  const [isIndicatorsLoading, setIsIndicatorsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('chart'); 
  
  // استیت‌های چارت استاندارد
  const [selectedSym, setSelectedSym] = useState('');
  const [normalChartData, setNormalChartData] = useState([]);
  const [loadingChart, setLoadingChart] = useState(false);

  // 🧪 استیت‌های آزمایشگاه فرمول‌نویسی
  const [variables, setVariables] = useState([{ id: 'A', symbol: '' }, { id: 'B', symbol: '' }]);
  const [formula, setFormula] = useState('(A / B) * 100');
  const [labChartData, setLabChartData] = useState([]);
  const [loadingLab, setLoadingLab] = useState(false);

  // لود سریع تمام شاخص‌ها در ابتدای کار
  useEffect(() => {
    setIsIndicatorsLoading(true);
    // اینجا تمام شاخص‌ها را می‌گیریم (بدون فیلتر) تا کاربر بداند چه چیزهایی در دیتابیس دارد
    axios.get(`${API_BASE}/data/symbols/available?limit=2000`)
      .then(res => {
        setIndicators(res.data);
        setIsIndicatorsLoading(false);
      })
      .catch(err => {
        console.error("خطا در دریافت شاخص‌ها:", err);
        setIsIndicatorsLoading(false);
      });
  }, []);

  // دریافت دیتای چارت استاندارد
  useEffect(() => {
    if (selectedSym && activeTab === 'chart') {
      setLoadingChart(true);
      axios.get(`${API_BASE}/data/${selectedSym}`)
        .then(res => {
          setNormalChartData(res.data.data);
          setLoadingChart(false);
        }).catch(() => setLoadingChart(false));
    }
  }, [selectedSym, activeTab]);

  // توابع مدیریت متغیرهای آزمایشگاه
  const addVariable = () => {
    const nextChar = String.fromCharCode(65 + variables.length); // تبدیل به C, D, E...
    setVariables([...variables, { id: nextChar, symbol: '' }]);
  };

  const updateVariable = (id, newSymbol) => {
    setVariables(variables.map(v => v.id === id ? { ...v, symbol: newSymbol } : v));
  };

  const removeVariable = (id) => {
    setVariables(variables.filter(v => v.id !== id));
  };

  // 🚀 شلیک فرمول به سمت موتور بک‌اند
  const runFormulaExperiment = () => {
    const varsDict = {};
    let hasEmpty = false;
    variables.forEach(v => {
      if (!v.symbol) hasEmpty = true;
      varsDict[v.id] = v.symbol;
    });

    if (hasEmpty) return alert("لطفاً نماد تمام متغیرها را انتخاب کنید.");
    if (!formula) return alert("لطفاً فرمول ریاضی را وارد کنید.");

    setLoadingLab(true);
    axios.post(`${API_BASE}/data/lab/formula`, {
      formula: formula,
      variables: varsDict
    }).then(res => {
      if (res.data.length === 0) alert("تاریخ مشترکی بین این شاخص‌ها یافت نشد یا دیتا ناقص است.");
      setLabChartData(res.data);
      setLoadingLab(false);
    }).catch(err => {
      alert("خطا در اجرای فرمول! مطمئن شوید فرمول ریاضی (مثل A/B) درست نوشته شده است.");
      setLoadingLab(false);
    });
  };

  return (
    <div className="flex h-screen bg-[#0b1120] text-slate-300 font-sans overflow-hidden">
      
      {/* 🧭 سایدبار (منوی کناری) */}
      <aside className="w-64 bg-[#0f172a] border-l border-slate-800 flex flex-col shadow-2xl z-10">
        <div className="p-6 border-b border-slate-800 flex items-center gap-3 text-blue-500">
          <Activity size={28} className="animate-pulse" />
          <h1 className="text-xl font-bold tracking-tight text-white">کوانت<span className="text-blue-500">لاب</span></h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <button onClick={() => setActiveTab('chart')} 
            className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all ${activeTab === 'chart' ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]' : 'hover:bg-slate-800/50 hover:text-white'}`}>
            <ChartIcon size={20} /> داشبورد بازار
          </button>
          <button onClick={() => setActiveTab('lab')} 
            className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all ${activeTab === 'lab' ? 'bg-purple-600/10 text-purple-400 border border-purple-500/20 shadow-[0_0_15px_rgba(147,51,234,0.1)]' : 'hover:bg-slate-800/50 hover:text-white'}`}>
            <FlaskConical size={20} /> آزمایشگاه فرمول
          </button>
        </nav>
        <div className="p-4 border-t border-slate-800 text-xs text-slate-500 text-center">
          دیتابیس متصل: {isIndicatorsLoading ? '...' : indicators.length} شاخص
        </div>
      </aside>

      {/* 🖥️ صفحه اصلی */}
      <main className="flex-1 p-8 overflow-y-auto relative">
        
        {/* افکت‌های نوری پس‌زمینه */}
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/10 blur-[120px] rounded-full pointer-events-none"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/10 blur-[120px] rounded-full pointer-events-none"></div>

        {/* =========================================================
            بخش ۱: چارت استاندارد بازار
        ========================================================= */}
        {activeTab === 'chart' && (
          <div className="relative z-10 animate-fade-in">
            <h2 className="text-2xl font-bold text-white mb-6">مرورگر شاخص‌های جهانی</h2>
            
            <div className="bg-[#1e293b]/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl mb-6">
              <label className="block text-sm text-slate-400 mb-2">جستجو و انتخاب نماد:</label>
              {isIndicatorsLoading ? (
                <div className="h-12 flex items-center text-blue-400 animate-pulse bg-[#0f172a] rounded-xl px-4">در حال بارگذاری کاتالوگ دیتابیس...</div>
              ) : (
                <select className="w-full bg-[#0f172a] border border-slate-600 rounded-xl p-3 text-white outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                  value={selectedSym} onChange={e => setSelectedSym(e.target.value)}>
                  <option value="">-- یک شاخص اقتصادی را انتخاب کنید --</option>
                  {indicators.map(ind => (
                    <option key={ind.id} value={ind.symbol}>
                      {ind.source} | {ind.symbol} | {ind.name.substring(0, 80)}... {ind.has_data ? '(✅)' : '(⏳ بدون دیتا)'}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="bg-[#1e293b]/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl h-[550px]">
              {loadingChart ? <div className="flex h-full items-center justify-center text-blue-400 animate-pulse text-lg">در حال استخراج تاریخچه...</div> : 
                normalChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={normalChartData}>
                    <defs>
                      <linearGradient id="colorNorm" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.5}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} vertical={false} />
                    <XAxis dataKey="date" stroke="#64748b" minTickGap={40} tick={{fontSize: 12}} />
                    <YAxis stroke="#64748b" domain={['auto', 'auto']} tick={{fontSize: 12}} />
                    <Tooltip contentStyle={{backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '12px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'}} />
                    <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={3} fill="url(#colorNorm)" />
                  </AreaChart>
                </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-slate-500">شاخصی انتخاب نشده یا دیتایی برای نمایش وجود ندارد.</div>
                )
              }
            </div>
          </div>
        )}

        {/* =========================================================
            بخش ۲: آزمایشگاه فرمول‌نویسی (Quant Lab)
        ========================================================= */}
        {activeTab === 'lab' && (
          <div className="relative z-10 animate-fade-in">
            <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-3">
              <Calculator className="text-purple-500" />
              محیط فرمول‌نویسی آزاد
            </h2>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
              
              {/* پنل تعریف متغیرها */}
              <div className="lg:col-span-1 bg-[#1e293b]/50 backdrop-blur-md p-6 rounded-2xl border border-purple-900/30 shadow-xl flex flex-col">
                <h3 className="text-lg font-semibold text-purple-400 mb-4 border-b border-slate-700 pb-2">۱. تعریف متغیرها</h3>
                
                <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
                  {variables.map((v) => (
                    <div key={v.id} className="bg-[#0f172a] p-3 rounded-xl border border-slate-700 flex items-center gap-3 group">
                      <div className="bg-purple-600/20 text-purple-400 font-bold w-8 h-8 rounded-lg flex items-center justify-center border border-purple-500/30">
                        {v.id}
                      </div>
                      <select className="flex-1 bg-transparent text-sm text-white outline-none w-full"
                        value={v.symbol} onChange={(e) => updateVariable(v.id, e.target.value)}>
                        <option value="" className="bg-slate-800">انتخاب نماد...</option>
                        {indicators.filter(i => i.has_data).map(ind => (
                          <option key={ind.id} value={ind.symbol} className="bg-slate-800">{ind.symbol}</option>
                        ))}
                      </select>
                      {variables.length > 2 && (
                        <button onClick={() => removeVariable(v.id)} className="text-slate-500 hover:text-red-400 transition-colors">
                          <Trash2 size={18} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                
                <button onClick={addVariable} className="mt-4 w-full py-3 rounded-xl border border-dashed border-slate-600 text-slate-400 hover:text-purple-400 hover:border-purple-500/50 transition-all flex items-center justify-center gap-2">
                  <Plus size={18} /> افزودن متغیر جدید
                </button>
              </div>

              {/* پنل فرمول‌نویسی و چارت */}
              <div className="lg:col-span-2 flex flex-col gap-6">
                
                {/* باکس فرمول */}
                <div className="bg-[#1e293b]/50 backdrop-blur-md p-6 rounded-2xl border border-purple-900/30 shadow-xl">
                  <h3 className="text-lg font-semibold text-purple-400 mb-4 border-b border-slate-700 pb-2">۲. نوشتن فرمول ریاضی</h3>
                  <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
                    <div className="flex-1 relative w-full">
                      <span className="absolute left-4 top-1/2 -translate-y-1/2 text-purple-500 font-bold text-xl">ƒ(x) =</span>
                      <input 
                        type="text" 
                        className="w-full bg-[#0f172a] border border-purple-500/30 rounded-xl py-4 pl-16 pr-4 text-white text-lg font-mono outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all"
                        placeholder="مثال: (A / B) * 100"
                        value={formula}
                        onChange={(e) => setFormula(e.target.value)}
                      />
                    </div>
                    <button onClick={runFormulaExperiment}
                      className="w-full md:w-auto bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-bold py-4 px-8 rounded-xl shadow-lg shadow-purple-500/20 transition-all">
                      اجرا و رسم چارت
                    </button>
                  </div>
                  <p className="mt-3 text-xs text-slate-500">راهنما: از متغیرهای <span className="text-purple-400 font-mono">A, B, C</span> و عملگرهای <span className="font-mono text-purple-400">+ - * /</span> و پرانتز <span className="font-mono text-purple-400">()</span> استفاده کنید.</p>
                </div>

                {/* چارت ترکیبی */}
                <div className="bg-[#1e293b]/50 backdrop-blur-md p-6 rounded-2xl border border-purple-900/30 shadow-xl h-[380px] flex-1">
                  {loadingLab ? <div className="flex h-full items-center justify-center text-purple-400 animate-pulse text-lg">در حال ترکیب و پردازش دیتا...</div> : 
                    labChartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={labChartData}>
                        <defs>
                          <linearGradient id="colorLab" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#a855f7" stopOpacity={0.5}/>
                            <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.4} vertical={false} />
                        <XAxis dataKey="date" stroke="#64748b" minTickGap={40} tick={{fontSize: 12}} />
                        <YAxis stroke="#64748b" domain={['auto', 'auto']} tick={{fontSize: 12}} />
                        <Tooltip contentStyle={{backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '12px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)'}} />
                        <Area type="monotone" dataKey="value" stroke="#a855f7" strokeWidth={3} fill="url(#colorLab)" />
                      </AreaChart>
                    </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full items-center justify-center text-slate-500">فرمول را اجرا کنید تا نتیجه در اینجا رسم شود.</div>
                    )
                  }
                </div>
              </div>

            </div>
          </div>
        )}

      </main>
    </div>
  );
}