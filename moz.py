import os
import shutil
import subprocess

def run_cmd(cmd, cwd=None):
    print(f"\n⚙️ در حال اجرا: {cmd}")
    subprocess.run(cmd, shell=True, cwd=cwd)

print("🧹 مرحله ۱: پاکسازی گندکاری‌های پوشه روت...")
files_to_delete = ['package.json', 'package-lock.json', 'tailwind.config.js', 'postcss.config.js']
for f in files_to_delete:
    if os.path.exists(f):
        os.remove(f)
        print(f"   🗑️ فایل {f} حذف شد.")

if os.path.exists('node_modules'):
    shutil.rmtree('node_modules')
    print("   🗑️ پوشه مزاحم node_modules حذف شد.")

print("\n🚀 مرحله ۲: ساخت پایه پروژه React (Vite)...")
run_cmd("npm create vite@latest ui-dashboard -- --template react")

ui_dir = "ui-dashboard"

print("\n📦 مرحله ۳: نصب پکیج‌های اصلی و Tailwind نسخه ۳...")
run_cmd("npm install", cwd=ui_dir)
run_cmd("npm install recharts lucide-react axios", cwd=ui_dir)
run_cmd("npm install -D tailwindcss@3 postcss autoprefixer", cwd=ui_dir)
run_cmd("npx tailwindcss init -p", cwd=ui_dir)

print("\n✍️ مرحله ۴: تزریق کدهای اختصاصی داشبورد...")

# --- محتوای فایل tailwind.config.js ---
tailwind_code = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}"""

# --- محتوای فایل index.css ---
css_code = """@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  background-color: #0f172a;
  color: #f8fafc;
}"""

# --- محتوای فایل App.jsx ---
app_code = """import { useState, useEffect } from 'react';
import axios from 'axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FlaskConical, LineChart as ChartIcon, Activity } from 'lucide-react';

const API_BASE = "http://localhost:8000/api";

export default function App() {
  const [indicators, setIndicators] = useState([]);
  const [mode, setMode] = useState('normal'); 
  
  const [selectedSym, setSelectedSym] = useState('');
  const [normalChartData, setNormalChartData] = useState([]);
  const [loading, setLoading] = useState(false);

  const [labSym1, setLabSym1] = useState('');
  const [labSym2, setLabSym2] = useState('');
  const [operation, setOperation] = useState('div');
  const [labChartData, setLabChartData] = useState([]);

  useEffect(() => {
    axios.get(`${API_BASE}/data/symbols/available?with_data_only=true&limit=2000`)
      .then(res => setIndicators(res.data))
      .catch(err => console.error("خطا:", err));
  }, []);

  useEffect(() => {
    if (selectedSym && mode === 'normal') {
      setLoading(true);
      axios.get(`${API_BASE}/data/${selectedSym}`)
        .then(res => {
          setNormalChartData(res.data.data);
          setLoading(false);
        }).catch(() => setLoading(false));
    }
  }, [selectedSym, mode]);

  const runLabExperiment = () => {
    if (!labSym1 || !labSym2) return alert("لطفاً هر دو شاخص را انتخاب کنید!");
    setLoading(true);
    axios.get(`${API_BASE}/data/lab/combine`, {
      params: { sym1: labSym1, sym2: labSym2, operation: operation }
    }).then(res => {
      setLabChartData(res.data);
      setLoading(false);
    }).catch(() => {
      alert("خطا در ترکیب دیتا!");
      setLoading(false);
    });
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 font-sans border-t-4 border-blue-500">
      <header className="flex flex-col md:flex-row justify-between items-center mb-8 border-b border-slate-700 pb-4 gap-4">
        <h1 className="text-3xl font-bold flex items-center gap-3 text-blue-400">
          <Activity size={32} />
          داشبورد اقتصاد جهانی
        </h1>
        <div className="flex gap-2 bg-slate-800 p-1 rounded-lg">
          <button onClick={() => setMode('normal')} className={`px-6 py-2 rounded-md flex items-center gap-2 transition-all ${mode === 'normal' ? 'bg-blue-600 shadow-lg' : 'hover:bg-slate-700'}`}>
            <ChartIcon size={18} /> چارت استاندارد
          </button>
          <button onClick={() => setMode('lab')} className={`px-6 py-2 rounded-md flex items-center gap-2 transition-all ${mode === 'lab' ? 'bg-purple-600 shadow-lg' : 'hover:bg-slate-700'}`}>
            <FlaskConical size={18} /> آزمایشگاه ترکیبی
          </button>
        </div>
      </header>

      {mode === 'normal' && (
        <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-2xl">
          <div className="mb-6">
            <label className="block text-sm text-slate-400 mb-2">انتخاب شاخص اقتصادی:</label>
            <select className="w-full bg-slate-900 border border-slate-600 rounded-lg p-3 outline-none focus:border-blue-500" value={selectedSym} onChange={e => setSelectedSym(e.target.value)}>
              <option value="">-- انتخاب کنید --</option>
              {indicators.map(ind => (
                <option key={ind.id} value={ind.symbol}>{ind.source} | {ind.name}</option>
              ))}
            </select>
          </div>
          <div className="h-[500px] w-full">
            {loading ? <div className="flex h-full items-center justify-center text-blue-400 animate-pulse">در حال استخراج...</div> : 
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={normalChartData}>
                  <defs>
                    <linearGradient id="colorNorm" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/><stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="date" stroke="#94a3b8" minTickGap={30} />
                  <YAxis stroke="#94a3b8" domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{backgroundColor: '#1e293b', border: 'none', borderRadius: '8px'}} />
                  <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} fill="url(#colorNorm)" />
                </AreaChart>
              </ResponsiveContainer>
            }
          </div>
        </div>
      )}

      {mode === 'lab' && (
        <div className="bg-slate-800 p-6 rounded-xl border border-purple-900/50 shadow-[0_0_30px_rgba(147,51,234,0.15)]">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr_auto] gap-4 items-end mb-6 bg-slate-900 p-4 rounded-lg">
            <div>
              <label className="block text-sm text-purple-400 mb-2">شاخص پایه (A):</label>
              <select className="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 outline-none" value={labSym1} onChange={e => setLabSym1(e.target.value)}>
                <option value="">انتخاب شاخص اول</option>
                {indicators.map(ind => <option key={`A-${ind.id}`} value={ind.symbol}>{ind.symbol} - {ind.name}</option>)}
              </select>
            </div>
            <div className="pb-1">
              <select className="bg-purple-600 font-bold rounded-lg p-3 outline-none cursor-pointer" value={operation} onChange={e => setOperation(e.target.value)}>
                <option value="div">÷ (تقسیم)</option><option value="mul">× (ضرب)</option>
                <option value="sub">- (تفریق)</option><option value="add">+ (جمع)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-purple-400 mb-2">شاخص دوم (B):</label>
              <select className="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 outline-none" value={labSym2} onChange={e => setLabSym2(e.target.value)}>
                <option value="">انتخاب شاخص دوم</option>
                {indicators.map(ind => <option key={`B-${ind.id}`} value={ind.symbol}>{ind.symbol} - {ind.name}</option>)}
              </select>
            </div>
            <button onClick={runLabExperiment} className="bg-purple-600 hover:bg-purple-500 font-bold py-3 px-8 rounded-lg transition-all mb-1">
              ترکیب کن! 🧪
            </button>
          </div>
          <div className="h-[500px] w-full mt-4">
            {loading ? <div className="flex h-full items-center justify-center text-purple-400 animate-pulse">در حال ترکیب و پردازش دیتا...</div> : 
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={labChartData}>
                  <defs>
                    <linearGradient id="colorLab" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#9333ea" stopOpacity={0.4}/><stop offset="95%" stopColor="#9333ea" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis dataKey="date" stroke="#94a3b8" minTickGap={30} />
                  <YAxis stroke="#94a3b8" domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{backgroundColor: '#1e293b', border: 'none', borderRadius: '8px'}} />
                  <Area type="step" dataKey="value" stroke="#9333ea" strokeWidth={2} fill="url(#colorLab)" />
                </AreaChart>
              </ResponsiveContainer>
            }
          </div>
        </div>
      )}
    </div>
  );
}"""

# تزریق کدها به فایل‌ها
with open(os.path.join(ui_dir, "tailwind.config.js"), "w", encoding="utf-8") as f:
    f.write(tailwind_code)

with open(os.path.join(ui_dir, "src", "index.css"), "w", encoding="utf-8") as f:
    f.write(css_code)

with open(os.path.join(ui_dir, "src", "App.jsx"), "w", encoding="utf-8") as f:
    f.write(app_code)

print("\n🎉 بوم! همه چیز با موفقیت نصب و جایگذاری شد.")
print("=====================================================")
print("حالا کافیست این دو دستور را بزنی تا داشبورد بالا بیاید:")
print("1. cd ui-dashboard")
print("2. npm run dev")