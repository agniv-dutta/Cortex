import React from 'react';
import type { StatsCardsProps } from '../types/dashboard';
import { TrendingUp, Clock, AlertCircle, ShieldAlert } from 'lucide-react';

export const StatsCards: React.FC<StatsCardsProps> = ({
  stats = {
    queriesWeek: 12,
    avgTime: '2.3 hrs',
    pendingApprovals: 3,
    alerts: 1,
  },
}) => {
  const cards = [
    {
      id: 'queries-week',
      label: 'Decisions This Week',
      value: stats.queriesWeek,
      unit: '',
      icon: TrendingUp,
      accentColor: 'text-amber-600',
      bgColor: 'bg-amber-50',
    },
    {
      id: 'avg-time',
      label: 'Avg Decision Time',
      value: stats.avgTime,
      unit: '',
      icon: Clock,
      accentColor: 'text-slate-700',
      bgColor: 'bg-slate-100',
    },
    {
      id: 'pending-approvals',
      label: 'Pending Approvals',
      value: stats.pendingApprovals,
      unit: '',
      icon: AlertCircle,
      accentColor: 'text-amber-700',
      bgColor: 'bg-amber-100/60',
    },
    {
      id: 'risk-alerts',
      label: 'Risk Alerts',
      value: stats.alerts,
      unit: '',
      icon: ShieldAlert,
      accentColor: 'text-rose-600',
      bgColor: 'bg-rose-50',
    },
  ];

  return (
    <section 
      className="w-full max-w-6xl mx-auto px-4 mb-8"
      aria-label="Key Performance Indicators"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-5">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.id}
              className="
                bg-white p-5 lg:p-6 rounded-2xl border border-gray-200/80 shadow-xs hover:shadow-md hover:-translate-y-0.5
                transition-all duration-200 flex flex-col justify-between group cursor-default
              "
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-slate-600 tracking-tight">
                  {card.label}
                </span>
                <div className={`p-2 rounded-xl ${card.bgColor} transition-transform group-hover:scale-110`}>
                  <Icon className={`w-4 h-4 ${card.accentColor}`} />
                </div>
              </div>

              <div className="flex items-baseline gap-1.5">
                <span className="text-3xl lg:text-4xl font-bold tracking-tight text-[#1F2937] font-sans">
                  {card.value}
                </span>
                {card.unit && (
                  <span className="text-sm font-medium text-slate-500">
                    {card.unit}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
