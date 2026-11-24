import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Database,
  Download,
  Info,
  Layers,
  ShieldCheck,
  Sliders,
  Upload,
} from "lucide-react";
import {
  API_BASE,
  askAI,
  confirmMappings,
  fetchInsights,
  fetchProfile,
  fetchQuality,
  loadDemoDataset,
  queryDashboard,
  runWhatIf,
  uploadDatasetFile,
} from "./api";
import { EChartCard } from "./components/EChartCard";

type NavTab = "overview" | "intelligence" | "ai" | "whatif" | "settings";

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("overview");
  const [demoMode, setDemoMode] = useState<boolean>(true);
  const [loadingBanner, setLoadingBanner] = useState<string>("");
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [datasetName, setDatasetName] = useState<string>("");
  const [domain, setDomain] = useState<string>("sales");

  const [profileData, setProfileData] = useState<any>(null);
  const [qualityData, setQualityData] = useState<any>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [insightsData, setInsightsData] = useState<any>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});

  // Semantic mapping confirmation state
  const [grainDraft, setGrainDraft] = useState<string>("line_item");
  const [mappingDrafts, setMappingDrafts] = useState<Record<string, string>>({});

  // AI Analyst state
  const [aiQuestion, setAiQuestion] = useState<string>("Break down revenue by region and highlight risks");
  const [aiResponse, setAiResponse] = useState<any>(null);
  const [showQueryEvidence, setShowQueryEvidence] = useState<boolean>(true);

  // What-If Simulator state
  const [pricePct, setPricePct] = useState<number>(5);
  const [volPct, setVolPct] = useState<number>(0);
  const [cogsPct, setCogsPct] = useState<number>(0);
  const [opexPct, setOpexPct] = useState<number>(-5);
  const [whatIfOut, setWhatIfOut] = useState<any>(null);

  const hydrateDataset = async (id: string, activeFilters: Record<string, string> = {}) => {
    setLoadingBanner("Waking analytical engine and computing deterministic KPIs...");
    try {
      const [prof, qual, dash, ins] = await Promise.all([
        fetchProfile(id, demoMode),
        fetchQuality(id, demoMode),
        queryDashboard(id, activeFilters, demoMode),
        fetchInsights(id, demoMode),
      ]);
      setProfileData(prof);
      setQualityData(qual.quality);
      setDashboardData(dash);
      setInsightsData(ins);
      setDatasetName(prof.name);
      setDomain(prof.domain);
      setGrainDraft(prof.grain || "line_item");
      const mapInit: Record<string, string> = {};
      (prof.mappings || []).forEach((m: any) => {
        mapInit[m.source_column] = m.canonical_concept;
      });
      setMappingDrafts(mapInit);
    } finally {
      setLoadingBanner("");
    }
  };

  const handleLoadDemo = async (sampleKey: string) => {
    setLoadingBanner("Loading One-Click Demo workspace...");
    setFilters({});
    setAiResponse(null);
    try {
      const res = await loadDemoDataset(sampleKey, demoMode);
      setDatasetId(res.dataset_id);
      await hydrateDataset(res.dataset_id, {});
      if (sampleKey === "nova_cryptic") setActiveTab("intelligence");
    } finally {
      setLoadingBanner("");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoadingBanner("Validating upload, scanning headers/totals, and archiving Parquet...");
    try {
      const res = await uploadDatasetFile(file, demoMode);
      setDatasetId(res.dataset_id);
      setFilters({});
      await hydrateDataset(res.dataset_id, {});
      setActiveTab("intelligence");
    } finally {
      setLoadingBanner("");
    }
  };

  const handleConfirmMappings = async () => {
    if (!datasetId) return;
    setLoadingBanner("Saving confirmed schema signature and recalculating KPIs...");
    try {
      const payload = Object.entries(mappingDrafts).map(([source_column, canonical_concept]) => ({
        source_column,
        canonical_concept,
      }));
      await confirmMappings(datasetId, grainDraft, payload, demoMode);
      await hydrateDataset(datasetId, filters);
      setActiveTab("overview");
    } finally {
      setLoadingBanner("");
    }
  };

  const handleFilterChange = async (dim: string, val: string) => {
    if (!datasetId) return;
    const next = { ...filters };
    if (!val || val === "All" || next[dim] === val) {
      delete next[dim];
    } else {
      next[dim] = val;
    }
    setFilters(next);
    const dash = await queryDashboard(datasetId, next, demoMode);
    setDashboardData(dash);
  };

  const handleAskAI = async () => {
    if (!datasetId || !aiQuestion.trim()) return;
    setLoadingBanner("Validating JSON AST query plan and retrieving verified evidence...");
    try {
      const ans = await askAI(datasetId, aiQuestion, demoMode);
      setAiResponse(ans);
    } finally {
      setLoadingBanner("");
    }
  };

  const handleSimulate = async () => {
    const kpis = dashboardData?.kpis?.kpis || [];
    const rev = kpis.find((k: any) => k.code.includes("TOTAL_REVENUE"))?.value || 2500000;
    const gp = kpis.find((k: any) => k.code.includes("GROSS_PROFIT"))?.value || rev * 0.45;
    const cogs = rev - gp;
    const opex = kpis.find((k: any) => k.code === "FIN_OPEX")?.value || rev * 0.22;
    const res = await runWhatIf(
      {
        baseline_revenue: rev,
        baseline_cogs: cogs,
        baseline_opex: opex,
        price_change_pct: pricePct,
        volume_change_pct: volPct,
        cogs_change_pct: cogsPct,
        opex_change_pct: opexPct,
      },
      demoMode
    );
    setWhatIfOut(res);
  };

  useEffect(() => {
    handleLoadDemo("acme_retail");
  }, []);

  const trendOption = useMemo(() => {
    const t = dashboardData?.analytics?.trend || [];
    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", backgroundColor: "#0F172A", borderColor: "#1F2937", textStyle: { color: "#F1F5F9" } },
      grid: { left: 56, right: 20, top: 20, bottom: 32 },
      xAxis: { type: "category", data: t.map((x: any) => x.period), axisLabel: { color: "#94A3B8" }, axisLine: { lineStyle: { color: "#1F2937" } } },
      yAxis: { type: "value", axisLabel: { color: "#94A3B8" }, splitLine: { lineStyle: { color: "#1F2937" } } },
      series: [
        {
          name: "Revenue",
          type: "line",
          smooth: true,
          data: t.map((x: any) => x.value),
          lineStyle: { color: "#06B6D4", width: 2.5 },
          itemStyle: { color: "#06B6D4" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(6,182,212,0.28)" },
                { offset: 1, color: "rgba(6,182,212,0.0)" },
              ],
            },
          },
        },
      ],
    };
  }, [dashboardData]);

  const breakdownKey = domain === "finance" ? "account_category" : "region";
  const breakdownOption = useMemo(() => {
    const items = dashboardData?.analytics?.breakdowns?.[breakdownKey] || [];
    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", backgroundColor: "#0F172A", borderColor: "#1F2937", textStyle: { color: "#F1F5F9" } },
      grid: { left: 60, right: 20, top: 18, bottom: 32 },
      xAxis: { type: "category", data: items.map((x: any) => x.name), axisLabel: { color: "#94A3B8" } },
      yAxis: { type: "value", axisLabel: { color: "#94A3B8" }, splitLine: { lineStyle: { color: "#1F2937" } } },
      series: [
        {
          type: "bar",
          barMaxWidth: 38,
          data: items.map((x: any) => x.value),
          itemStyle: { color: "#3B82F6", borderRadius: [4, 4, 0, 0] },
        },
      ],
    };
  }, [dashboardData, breakdownKey]);

  const waterfallOption = useMemo(() => {
    const wf = dashboardData?.analytics?.variance_waterfall || [];
    return {
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", backgroundColor: "#0F172A", borderColor: "#1F2937", textStyle: { color: "#F1F5F9" } },
      grid: { left: 60, right: 20, top: 18, bottom: 38 },
      xAxis: { type: "category", data: wf.map((w: any) => w.label), axisLabel: { color: "#94A3B8", interval: 0, rotate: 12 } },
      yAxis: { type: "value", axisLabel: { color: "#94A3B8" }, splitLine: { lineStyle: { color: "#1F2937" } } },
      series: [
        {
          type: "bar",
          barMaxWidth: 34,
          data: wf.map((w: any) => ({
            value: w.delta,
            itemStyle: {
              color: w.type === "total" ? "#8B5CF6" : w.delta >= 0 ? "#10B981" : "#F43F5E",
              borderRadius: [4, 4, 0, 0],
            },
          })),
        },
      ],
    };
  }, [dashboardData]);

  const topKpis = (dashboardData?.kpis?.kpis || []).slice(0, 6);

  return (
    <div className="min-h-screen flex bg-[#0A0E17] text-slate-100">
      {/* Left Sidebar */}
      <aside className="w-64 shrink-0 border-r border-[#1F2937] bg-[#0D1321] flex flex-col justify-between p-4">
        <div>
          <div className="flex items-center gap-2.5 px-2 pb-5 border-b border-[#1F2937]">
            <div className="h-8 w-8 rounded-lg bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="text-sm font-semibold tracking-tight text-white">PROJECT NEXUS</div>
              <div className="text-[11px] text-slate-400">Enterprise Intelligence v2.0</div>
            </div>
          </div>

          <nav className="mt-5 space-y-1">
            {[
              { id: "overview", label: "Executive Overview", icon: BarChart3 },
              { id: "intelligence", label: "Data Intelligence Centre", icon: Database },
              { id: "ai", label: "Grounded AI Analyst", icon: Bot },
              { id: "whatif", label: "What-If Simulator", icon: Sliders },
              { id: "settings", label: "Governance & Settings", icon: ShieldCheck },
            ].map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id as NavTab)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    active
                      ? "bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-neon-cyan"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60 border border-transparent"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* One-Click Demo Workspaces */}
          <div className="mt-7 pt-5 border-t border-[#1F2937]">
            <div className="px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
              One-Click Demo Workspaces
            </div>
            <div className="space-y-1.5">
              <button onClick={() => handleLoadDemo("acme_retail")} className="w-full text-left px-3 py-2 rounded-lg text-xs bg-[#111827] border border-[#1F2937] hover:border-cyan-500/50 text-slate-200">
                Acme Retail (Sales Line-Item)
              </button>
              <button onClick={() => handleLoadDemo("apex_finance")} className="w-full text-left px-3 py-2 rounded-lg text-xs bg-[#111827] border border-[#1F2937] hover:border-blue-500/50 text-slate-200">
                Apex SaaS (Financial P&L)
              </button>
              <button onClick={() => handleLoadDemo("nova_cryptic")} className="w-full text-left px-3 py-2 rounded-lg text-xs bg-[#111827] border border-[#1F2937] hover:border-violet-500/50 text-slate-200">
                Nova Corp (Cryptic Headers)
              </button>
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-[#1F2937] flex items-center justify-between px-2">
          <span className="text-xs text-slate-400">Public Demo Mode</span>
          <button
            onClick={() => setDemoMode(!demoMode)}
            className={`px-2.5 py-1 rounded text-xs font-medium border ${
              demoMode ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" : "bg-slate-800 text-slate-400 border-slate-700"
            }`}
          >
            {demoMode ? "Active" : "BYOK"}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        {loadingBanner && (
          <div className="mb-5 px-4 py-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-200 text-xs flex items-center gap-2">
            <Activity className="w-4 h-4 animate-spin" />
            <span>{loadingBanner}</span>
          </div>
        )}

        {/* Top Header */}
        <header className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-[#1F2937] mb-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">
              {datasetName || "No Dataset Loaded"}
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Domain: <span className="text-cyan-400 uppercase font-medium">{domain}</span>
              {" · "}Grain: <span className="text-slate-200">{profileData?.grain || "pending"}</span>
              {" · "}Quality Index: <span className="tabular-nums text-emerald-400 font-medium">{qualityData?.overall_score ?? "--"}/100</span>
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="cursor-pointer inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 hover:shadow-neon-cyan">
              <Upload className="w-3.5 h-3.5" />
              <span>Upload CSV / XLSX</span>
              <input type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={handleFileUpload} />
            </label>
            {datasetId && (
              <a
                href={`${API_BASE}/api/v1/dashboards/${datasetId}/export`}
                onClick={async (e) => {
                  e.preventDefault();
                  const res = await fetch(`${API_BASE}/api/v1/dashboards/${datasetId}/export`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-Demo-Mode": "true" },
                    body: JSON.stringify({ filters }),
                  });
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `nexus_export_${datasetId.slice(0, 8)}.csv`;
                  a.click();
                }}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium bg-[#111827] text-slate-200 border border-[#1F2937] hover:border-slate-500"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export Safe CSV</span>
              </a>
            )}
          </div>
        </header>

        {/* Critical Blocker Banner (ADR-04: Never Masked) */}
        {qualityData?.has_critical_blockers && (
          <div className="mb-6 p-4 rounded-lg bg-rose-500/10 border border-rose-500/40 text-rose-200 text-xs flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-rose-300">Critical Data Quality Blockers Detected</div>
              <ul className="mt-1 space-y-0.5 list-disc list-inside text-rose-200/90">
                {qualityData.critical_blockers.map((b: any, i: number) => (
                  <li key={i}>
                    {b.dimension}: {b.remediation}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* TAB 1: EXECUTIVE OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Synchronized Slicers */}
            {dashboardData?.analytics?.slicers && (
              <div className="flex flex-wrap items-center gap-3">
                {Object.entries(dashboardData.analytics.slicers).map(([dim, vals]: [string, any]) => (
                  <div key={dim} className="flex items-center gap-2 bg-[#111827] border border-[#1F2937] rounded-lg px-3 py-1.5">
                    <span className="text-[11px] uppercase tracking-wider text-slate-400">{dim.replace("_", " ")}</span>
                    <select
                      value={filters[dim] || "All"}
                      onChange={(e) => handleFilterChange(dim, e.target.value)}
                      className="bg-transparent text-xs text-cyan-300 focus:outline-none"
                    >
                      <option value="All" className="bg-[#111827]">All</option>
                      {(vals as string[]).map((v) => (
                        <option key={v} value={v} className="bg-[#111827]">{v}</option>
                      ))}
                    </select>
                  </div>
                ))}
                {Object.keys(filters).length > 0 && (
                  <button
                    onClick={() => {
                      setFilters({});
                      if (datasetId) hydrateDataset(datasetId, {});
                    }}
                    className="text-xs text-cyan-400 hover:underline"
                  >
                    Reset Filters
                  </button>
                )}
              </div>
            )}

            {/* Top-Row KPI Cards (Max 6 per ADR-08) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {topKpis.map((kpi: any) => (
                <div key={kpi.code} className="nexus-card p-5 relative group">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">{kpi.name}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full border ${
                        kpi.eligibility_status === "Calculable"
                          ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                          : kpi.eligibility_status === "Not Calculable"
                          ? "bg-rose-500/10 text-rose-300 border-rose-500/30"
                          : "bg-amber-500/10 text-amber-300 border-amber-500/30"
                      }`}
                    >
                      {kpi.eligibility_status}
                    </span>
                  </div>
                  <div className="mt-3 text-2xl font-semibold tabular-nums text-white">{kpi.formatted_value}</div>
                  <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
                    <Info className="w-3.5 h-3.5 text-cyan-400" />
                    <span className="truncate">{kpi.trust_tooltip?.formula}</span>
                  </div>
                  {/* Trust Tooltip Popover on Hover */}
                  <div className="hidden group-hover:block absolute z-20 left-0 right-0 top-full mt-2 p-3.5 rounded-lg bg-[#0F172A] border border-cyan-500/40 shadow-xl text-[11px] space-y-1 text-slate-300">
                    <div><strong className="text-cyan-300">Formula:</strong> {kpi.trust_tooltip?.formula}</div>
                    <div><strong className="text-cyan-300">Source Columns:</strong> {(kpi.trust_tooltip?.source_columns || []).join(", ") || "None"}</div>
                    <div><strong className="text-cyan-300">Excluded Rows:</strong> {kpi.trust_tooltip?.excluded_row_count}</div>
                    <div><strong className="text-cyan-300">Version:</strong> {kpi.trust_tooltip?.calculation_version}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <EChartCard title="Period Performance Trend" subtitle="Deterministic monthly aggregation" option={trendOption} />
              <EChartCard
                title={`Breakdown by ${breakdownKey.replace("_", " ")}`}
                subtitle="Click any bar to cross-filter all KPIs & charts"
                option={breakdownOption}
                onItemClick={(val) => handleFilterChange(breakdownKey, val)}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <EChartCard title="Revenue Variance Waterfall" subtitle="First-half vs second-half period decomposition" option={waterfallOption} />
              <div className="nexus-card p-5">
                <h3 className="text-sm font-semibold text-slate-100 mb-3">Prioritized Weekly Executive Brief</h3>
                <div className="space-y-3">
                  {(insightsData?.ranked_findings || []).map((f: any, idx: number) => (
                    <div key={idx} className="p-3 rounded-lg bg-[#0A0E17] border border-[#1F2937]">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium text-slate-100">{f.title}</span>
                        <span className="tabular-nums text-[11px] text-cyan-400">Priority {f.priority_score}</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">{f.action}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: DATA INTELLIGENCE CENTRE */}
        {activeTab === "intelligence" && (
          <div className="space-y-6">
            {/* 7-Dimension Quality Scorecard */}
            <div className="nexus-card p-5">
              <h2 className="text-sm font-semibold text-white mb-4">7-Dimension Data Quality Scorecard</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {(qualityData?.dimensions || []).map((d: any) => (
                  <div key={d.dimension} className="p-3.5 rounded-lg bg-[#0A0E17] border border-[#1F2937]">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-200">{d.dimension}</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded ${
                          d.severity === "Critical Blocker"
                            ? "bg-rose-500/15 text-rose-300"
                            : d.severity === "Warning"
                            ? "bg-amber-500/15 text-amber-300"
                            : "bg-emerald-500/15 text-emerald-300"
                        }`}
                      >
                        {d.severity}
                      </span>
                    </div>
                    <div className="text-xl font-semibold tabular-nums text-white mt-2">{d.score}%</div>
                    <p className="text-[11px] text-slate-400 mt-1.5">{d.remediation}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Hybrid Semantic Mapper & Grain Confirmation */}
            <div className="nexus-card p-5">
              <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-sm font-semibold text-white">Hybrid Semantic Mapper & Dataset Grain Confirmation</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {profileData?.profile?.grain_discovery?.reason}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <select
                    value={grainDraft}
                    onChange={(e) => setGrainDraft(e.target.value)}
                    className="bg-[#0A0E17] border border-[#1F2937] rounded-lg px-3 py-1.5 text-xs text-cyan-300"
                  >
                    <option value="line_item">Grain: Line Item (Multi-line Orders)</option>
                    <option value="order">Grain: Single Order per Row</option>
                    <option value="ledger_entry">Grain: Financial Ledger Entry</option>
                    <option value="employee_record">Grain: Employee Record</option>
                  </select>
                  <button
                    onClick={handleConfirmMappings}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-cyan-500 text-slate-950 hover:bg-cyan-400"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Confirm & Publish</span>
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-slate-400 border-b border-[#1F2937]">
                    <tr>
                      <th className="py-2.5 px-3">Source Column</th>
                      <th className="py-2.5 px-3">Sample Values</th>
                      <th className="py-2.5 px-3">Canonical Concept</th>
                      <th className="py-2.5 px-3">Confidence</th>
                      <th className="py-2.5 px-3">Tier</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1F2937]">
                    {(profileData?.mappings || []).map((m: any) => (
                      <tr key={m.source_column}>
                        <td className="py-2.5 px-3 font-mono text-slate-200">{m.source_column}</td>
                        <td className="py-2.5 px-3 text-slate-400">{(m.sample_values || []).slice(0, 3).join(", ")}</td>
                        <td className="py-2.5 px-3">
                          <input
                            value={mappingDrafts[m.source_column] || ""}
                            onChange={(e) =>
                              setMappingDrafts({ ...mappingDrafts, [m.source_column]: e.target.value })
                            }
                            className="bg-[#0A0E17] border border-[#1F2937] rounded px-2 py-1 text-xs text-cyan-300 w-44"
                          />
                        </td>
                        <td className="py-2.5 px-3 tabular-nums">{Math.round((m.confidence || 0) * 100)}%</td>
                        <td className="py-2.5 px-3 text-slate-400">{m.mapping_tier}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: GROUNDED AI ANALYST */}
        {activeTab === "ai" && (
          <div className="space-y-5 max-w-4xl">
            <div className="nexus-card p-5">
              <h2 className="text-sm font-semibold text-white mb-2">Grounded AI Business Analyst (Zero Hallucination Pipeline)</h2>
              <p className="text-xs text-slate-400 mb-4">
                100% of arithmetic runs deterministically in Python/DuckDB via validated JSON AST plans.
              </p>
              <div className="flex gap-3">
                <input
                  value={aiQuestion}
                  onChange={(e) => setAiQuestion(e.target.value)}
                  placeholder="Ask a business question (e.g., Break down revenue by region)..."
                  className="flex-1 bg-[#0A0E17] border border-[#1F2937] rounded-lg px-3.5 py-2.5 text-sm text-slate-100 focus:border-cyan-500/60 focus:outline-none"
                />
                <button
                  onClick={handleAskAI}
                  className="px-4 py-2.5 rounded-lg text-xs font-semibold bg-cyan-500 text-slate-950 hover:bg-cyan-400"
                >
                  Run Grounded Query
                </button>
              </div>
            </div>

            {aiResponse && (
              <div className="nexus-card p-5 space-y-4">
                <div className="flex items-center justify-between text-xs border-b border-[#1F2937] pb-3">
                  <span className="text-cyan-400 font-medium">Stage: {aiResponse.stage}</span>
                  <span className="text-slate-400">Mode: {aiResponse.execution_mode}</span>
                </div>
                <div className="space-y-3 text-xs leading-relaxed">
                  <div>
                    <div className="font-semibold text-emerald-400">1. Verified Observation & Evidence</div>
                    <p className="text-slate-200 mt-1">{aiResponse.structured_answer.verified_observation_and_evidence}</p>
                  </div>
                  <div>
                    <div className="font-semibold text-cyan-400">2. Business Impact</div>
                    <p className="text-slate-300 mt-1">{aiResponse.structured_answer.business_impact}</p>
                  </div>
                  <div>
                    <div className="font-semibold text-amber-400">3. Possible Explanations / Hypotheses (Unverified)</div>
                    <p className="text-slate-300 mt-1">{aiResponse.structured_answer.possible_explanations_hypotheses.join(" ")}</p>
                  </div>
                  <div>
                    <div className="font-semibold text-blue-400">4. Recommended Investigation & Actions</div>
                    <ul className="list-disc list-inside text-slate-300 mt-1">
                      {aiResponse.structured_answer.recommended_investigation_actions.map((a: string, i: number) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-400">5. Confidence & Data Limitations</div>
                    <p className="text-slate-400 mt-1">{aiResponse.structured_answer.confidence_and_data_limitations}</p>
                  </div>
                </div>

                <div className="pt-3 border-t border-[#1F2937]">
                  <button
                    onClick={() => setShowQueryEvidence(!showQueryEvidence)}
                    className="text-xs text-cyan-400 hover:underline"
                  >
                    {showQueryEvidence ? "Hide Query & Evidence Audit Panel" : "See the Query & Evidence"}
                  </button>
                  {showQueryEvidence && (
                    <pre className="mt-2 p-3 rounded-lg bg-[#0A0E17] border border-[#1F2937] text-[11px] text-slate-300 overflow-x-auto">
                      {JSON.stringify(aiResponse.see_the_query_and_evidence, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 4: WHAT-IF SIMULATOR */}
        {activeTab === "whatif" && (
          <div className="nexus-card p-6 max-w-3xl space-y-5">
            <div>
              <h2 className="text-sm font-semibold text-white">Transparent Formula-Driven What-If Simulator</h2>
              <p className="text-xs text-slate-400 mt-1">
                Strictly separates Historical Actuals, User Assumptions, and Scenario Outputs (arithmetic sensitivity, not predictive AI).
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              {[
                { label: "Price Change %", val: pricePct, set: setPricePct },
                { label: "Volume Change %", val: volPct, set: setVolPct },
                { label: "COGS Change %", val: cogsPct, set: setCogsPct },
                { label: "OpEx Change %", val: opexPct, set: setOpexPct },
              ].map((s) => (
                <div key={s.label} className="p-3 rounded-lg bg-[#0A0E17] border border-[#1F2937]">
                  <div className="flex justify-between mb-1.5">
                    <span className="text-slate-300">{s.label}</span>
                    <span className="tabular-nums text-cyan-400 font-semibold">{s.val > 0 ? `+${s.val}%` : `${s.val}%`}</span>
                  </div>
                  <input type="range" min={-30} max={30} value={s.val} onChange={(e) => s.set(Number(e.target.value))} className="w-full accent-cyan-400" />
                </div>
              ))}
            </div>
            <button onClick={handleSimulate} className="px-4 py-2 rounded-lg text-xs font-semibold bg-cyan-500 text-slate-950 hover:bg-cyan-400">
              Compute Scenario Outputs
            </button>
            {whatIfOut && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 text-xs">
                <div className="p-4 rounded-lg bg-[#0A0E17] border border-[#1F2937]">
                  <div className="text-slate-400 font-semibold mb-2">Historical Actuals</div>
                  <div className="tabular-nums space-y-1">
                    <div>Revenue: {whatIfOut.historical_actuals.revenue.toLocaleString()}</div>
                    <div>Gross Profit: {whatIfOut.historical_actuals.gross_profit.toLocaleString()}</div>
                    <div>Operating Profit: {whatIfOut.historical_actuals.operating_profit.toLocaleString()}</div>
                  </div>
                </div>
                <div className="p-4 rounded-lg bg-[#0A0E17] border border-cyan-500/40">
                  <div className="text-cyan-400 font-semibold mb-2">Scenario Outputs</div>
                  <div className="tabular-nums space-y-1">
                    <div>Revenue: {whatIfOut.scenario_outputs.revenue.toLocaleString()}</div>
                    <div>Gross Profit: {whatIfOut.scenario_outputs.gross_profit.toLocaleString()}</div>
                    <div>Operating Profit: {whatIfOut.scenario_outputs.operating_profit.toLocaleString()}</div>
                    <div className={whatIfOut.scenario_outputs.net_profit_delta >= 0 ? "text-emerald-400" : "text-rose-400"}>
                      Net Profit Delta: {whatIfOut.scenario_outputs.net_profit_delta >= 0 ? "+" : ""}
                      {whatIfOut.scenario_outputs.net_profit_delta.toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: GOVERNANCE & SETTINGS */}
        {activeTab === "settings" && (
          <div className="nexus-card p-6 max-w-2xl space-y-4 text-xs">
            <h2 className="text-sm font-semibold text-white">Organization Governance, BYOK AI & DPDP Controls</h2>
            <p className="text-slate-400">
              All tenant tables enforce organization_id isolation and PostgreSQL RLS. BYOK Gemini keys are Fernet-encrypted server-side and never exposed to frontend bundles.
            </p>
            <div className="p-4 rounded-lg bg-[#0A0E17] border border-[#1F2937] space-y-2">
              <div><strong className="text-slate-200">Active Role:</strong> Org Admin (MVP 2-Role + Demo Mode)</div>
              <div><strong className="text-slate-200">Storage Architecture:</strong> Immutable Raw + Columnar Apache Parquet + DuckDB</div>
              <div><strong className="text-slate-200">CSV Export Protection:</strong> Formula-Injection Neutralization (=, +, -, @) Active</div>
              <div><strong className="text-slate-200">Privacy Posture:</strong> India DPDP aligned (user-controlled deletion, audit logs, HR salary masking)</div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
