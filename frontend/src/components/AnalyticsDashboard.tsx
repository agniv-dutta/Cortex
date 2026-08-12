import React, { useState } from 'react';
import type { AnalyticsDashboardProps } from '../types/dashboard';
import { 
  mockAnalyticsMetrics, 
  mockVolumeTrend, 
  mockCategoryAccuracy, 
  mockOutcomeData, 
  mockAnalyticsInsights 
} from '../data/mockData';
import { 
  TrendingUp, 
  Clock, 
  CheckCircle2, 
  AlertTriangle, 
  Sparkles, 
  ArrowUpRight, 
  ArrowDownRight,
  BarChart3,
  PieChart as PieIcon,
  Calendar
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  ComposedChart, 
  Area, 
  Line, 
  XAxis, 
  YAxis, 
  Tooltip, 
  CartesianGrid, 
  BarChart, 
  Bar, 
  PieChart, 
  Pie, 
  Cell, 
  Legend 
} from 'recharts';

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({
  metrics = mockAnalyticsMetrics,
  chartData = {
    volumeTrend: mockVolumeTrend,
    accuracyByCategory: mockCategoryAccuracy,
    outcomes: mockOutcomeData,
  },
  insights = mockAnalyticsInsights,
  onRangeChange,
}) => {
  const [selectedRange, setSelectedRange] = useState<'7d' | '30d' | '90d'>('30d');

  const handleRangeChange = (range: '7d' | '30d' | '90d') => {
    setSelectedRange(range);
    if (onRangeChange) {
      onRangeChange(range);
    }
  };

  // Filter trend data based on selected range
  const filteredVolumeData = React.useMemo(() => {
    if (selectedRange === '7d') return chartData.volumeTrend.slice(-5);
    if (selectedRange === '90d') return [...chartData.volumeTrend, ...chartData.volumeTrend];
    return chartData.volumeTrend;
  }, [selectedRange, chartData.volumeTrend]);

  return (
    <div 
      className="w-full max-w-6xl mx-auto px-4 py-4 space-y-8 font-sans"
      role="region"
      aria-label="Cortex Analytics Dashboard"
    >
      {/* 1. Header & Date Range Filter Selector */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-gray-200/90 shadow-xs">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 className="w-5 h-5 text-amber-600" />
            <h1 className="text-2xl font-bold tracking-tight text-[#1F2937]">
              Analytics Overview
            </h1>
          </div>
          <p className="text-sm text-slate-500 font-medium">
            Real-time performance metrics and decision velocity for your team
          </p>
        </div>

        {/* Date Range Selector Pills */}
        <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-2xl border border-slate-200/80 self-start sm:self-auto">
          <Calendar className="w-4 h-4 text-slate-400 ml-2 mr-1" />
          {(['7d', '30d', '90d'] as const).map((range) => {
            const isActive = selectedRange === range;
            return (
              <button
                key={range}
                onClick={() => handleRangeChange(range)}
                className={`
                  px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all duration-200 uppercase tracking-wider
                  ${
                    isActive
                      ? 'bg-amber-600 text-white shadow-xs'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
                  }
                `}
              >
                {range}
              </button>
            );
          })}
        </div>
      </header>

      {/* 2. Top KPI Cards Row (4 Cards with 4px left border) */}
      <section 
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-5"
        aria-label="Key Analytics Metrics"
      >
        {/* KPI 1: Total Decisions */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/90 border-l-4 border-l-[#10B981] shadow-xs hover:shadow-md transition-all">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Total Decisions</span>
            <div className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-[#1F2937] tracking-tight mb-2">
            {metrics.totalDecisions}
          </div>
          <div className="flex items-center gap-1 text-xs font-semibold text-emerald-700">
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>+14.2% vs last month</span>
          </div>
        </div>

        {/* KPI 2: Avg Decision Time */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/90 border-l-4 border-l-[#D97706] shadow-xs hover:shadow-md transition-all">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Avg Decision Time</span>
            <div className="p-1.5 rounded-lg bg-amber-50 text-amber-600">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-[#1F2937] tracking-tight mb-2">
            {metrics.avgDecisionTime} <span className="text-sm font-medium text-slate-500">hrs</span>
          </div>
          <div className="flex items-center gap-1 text-xs font-semibold text-emerald-700">
            <ArrowDownRight className="w-3.5 h-3.5" />
            <span>-0.4 hrs faster</span>
          </div>
        </div>

        {/* KPI 3: Approval Rate */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/90 border-l-4 border-l-[#10B981] shadow-xs hover:shadow-md transition-all">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Approval Rate</span>
            <div className="p-1.5 rounded-lg bg-emerald-50 text-emerald-600">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-[#1F2937] tracking-tight mb-2">
            {metrics.approvalRate}%
          </div>
          <div className="flex items-center gap-1 text-xs font-semibold text-emerald-700">
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>+2.1% accuracy</span>
          </div>
        </div>

        {/* KPI 4: Risk Alerts */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200/90 border-l-4 border-l-[#D97706] shadow-xs hover:shadow-md transition-all">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-bold uppercase tracking-wider">Risk Alerts</span>
            <div className="p-1.5 rounded-lg bg-amber-50 text-amber-600">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-[#1F2937] tracking-tight mb-2">
            {metrics.riskAlerts} <span className="text-sm font-medium text-slate-500">Active</span>
          </div>
          <div className="flex items-center gap-1 text-xs font-semibold text-emerald-700">
            <ArrowDownRight className="w-3.5 h-3.5" />
            <span>-2 alerts resolved</span>
          </div>
        </div>
      </section>

      {/* 3. Area Chart: Volume & Velocity Trend over 30 Days */}
      <section className="bg-white p-6 lg:p-7 rounded-3xl border border-gray-200/90 shadow-xs">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-bold text-[#1F2937] tracking-tight">
              Decision Volume & Velocity Trend
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Amber line represents decision volume; Sage green shaded area tracks average turnaround velocity (hours)
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-semibold">
            <span className="flex items-center gap-1.5 text-amber-700">
              <span className="w-3 h-3 rounded-full bg-amber-600 inline-block" /> Decision Volume
            </span>
            <span className="flex items-center gap-1.5 text-emerald-700">
              <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" /> Avg Velocity (hrs)
            </span>
          </div>
        </div>

        <div className="w-full h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={filteredVolumeData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
              <XAxis dataKey="date" stroke="#94A3B8" fontSize={11} tickLine={false} />
              <YAxis yAxisId="left" stroke="#94A3B8" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis yAxisId="right" orientation="right" stroke="#94A3B8" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1F2937', 
                  borderColor: '#374151', 
                  borderRadius: '12px', 
                  color: '#FFFFFF',
                  fontSize: '12px',
                  boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)'
                }} 
              />
              <Area 
                yAxisId="right" 
                type="monotone" 
                dataKey="avgTime" 
                name="Avg Time (hrs)" 
                fill="#10B981" 
                stroke="#10B981" 
                fillOpacity={0.15} 
                strokeWidth={2}
              />
              <Line 
                yAxisId="left" 
                type="monotone" 
                dataKey="volume" 
                name="Decisions" 
                stroke="#D97706" 
                strokeWidth={3} 
                dot={{ r: 3, fill: '#D97706' }} 
                activeDot={{ r: 6 }} 
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* 4. Grid Row: Category Accuracy Bar Chart + Outcomes Donut Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
        
        {/* Left Card: Horizontal Bar Chart (Accuracy by Category) */}
        <section className="lg:col-span-7 bg-white p-6 rounded-3xl border border-gray-200/90 shadow-xs">
          <div className="mb-4">
            <h2 className="text-lg font-bold text-[#1F2937] tracking-tight">
              Decision Accuracy by Category
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Historical precision alignment percentage across enterprise business units
            </p>
          </div>

          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={chartData.accuracyByCategory} margin={{ top: 10, right: 30, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#94A3B8" fontSize={11} tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="category" stroke="#475569" fontSize={12} tickLine={false} axisLine={false} width={90} />
                <Tooltip 
                  formatter={(val: any) => [`${val}%`, 'Accuracy']}
                  contentStyle={{ backgroundColor: '#1F2937', borderRadius: '10px', color: '#FFF' }}
                />
                <Bar dataKey="accuracy" fill="#D97706" radius={[0, 8, 8, 0]} barSize={22}>
                  {chartData.accuracyByCategory.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.accuracy >= 92 ? '#D97706' : '#F59E0B'} 
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Right Card: Outcomes Donut Chart */}
        <section className="lg:col-span-5 bg-white p-6 rounded-3xl border border-gray-200/90 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-bold text-[#1F2937] tracking-tight flex items-center gap-2">
                <PieIcon className="w-4 h-4 text-amber-600" />
                Outcome Breakdown
              </h2>
              <span className="text-xs font-semibold text-slate-400">Distribution</span>
            </div>
            <p className="text-xs text-slate-500 font-medium mb-2">
              Status distribution across all active decisionBrief workflows
            </p>
          </div>

          <div className="w-full h-56 relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData.outcomes}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="count"
                  nameKey="status"
                >
                  {chartData.outcomes.map((entry, index) => (
                    <Cell key={`donut-${index}`} fill={entry.color || '#D97706'} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1F2937', borderRadius: '10px', color: '#FFF' }}
                />
                <Legend 
                  iconType="circle"
                  layout="horizontal"
                  verticalAlign="bottom"
                  align="center"
                  wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      {/* 5. Bottom Row: 3 Actionable Insight Cards */}
      <section 
        className="space-y-4"
        aria-labelledby="insights-heading"
      >
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-600" />
          <h2 id="insights-heading" className="text-lg font-bold text-[#1F2937] tracking-tight">
            AI Actionable Insights & Recommendations
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {insights.map((insightText, index) => (
            <div
              key={index}
              className="
                bg-[#FFFBEB] p-5 rounded-2xl border border-amber-200/80 border-l-4 border-l-[#D97706]
                shadow-2xs hover:shadow-xs transition-all duration-200 flex flex-col justify-between space-y-3
              "
            >
              <div className="flex items-center justify-between text-xs font-bold text-amber-900">
                <span className="uppercase tracking-wider">Insight #{index + 1}</span>
                <span className="px-2 py-0.5 rounded bg-amber-200/60 text-amber-900 text-[10px]">
                  High Impact
                </span>
              </div>

              <p className="text-xs sm:text-sm font-medium text-slate-800 leading-relaxed">
                {insightText}
              </p>

              <button
                onClick={() => alert(`Applying recommendation: "${insightText}"`)}
                className="text-xs font-bold text-amber-800 hover:text-amber-950 inline-flex items-center gap-1 self-start hover:underline pt-1"
              >
                <span>Apply Playbook</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default AnalyticsDashboard;
