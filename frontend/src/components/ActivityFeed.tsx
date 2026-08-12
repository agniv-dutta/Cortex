import React from 'react';
import type { ActivityFeedProps, DecisionItem, DecisionStatus } from '../types/dashboard';
import { CheckCircle2, Clock, XCircle, ChevronRight } from 'lucide-react';

export const ActivityFeed: React.FC<ActivityFeedProps> = ({
  decisions = [],
  onSelectDecision,
}) => {
  const getStatusBadge = (status: DecisionStatus) => {
    switch (status) {
      case 'Approved':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100/80 text-emerald-800 border border-emerald-300/60">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Approved
          </span>
        );
      case 'Pending':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100/80 text-amber-800 border border-amber-300/60">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            Pending
          </span>
        );
      case 'Rejected':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-100/80 text-rose-800 border border-rose-300/60">
            <XCircle className="w-3.5 h-3.5 text-rose-600" />
            Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  const handleRowClick = (decision: DecisionItem) => {
    if (onSelectDecision) {
      onSelectDecision(decision);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent, decision: DecisionItem) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleRowClick(decision);
    }
  };

  return (
    <section 
      className="w-full max-w-6xl mx-auto px-4 mb-12"
      aria-labelledby="recent-decisions-heading"
    >
      <div className="bg-white rounded-2xl border border-gray-200/90 shadow-xs overflow-hidden">
        {/* Table Header Section */}
        <div className="p-6 border-b border-gray-200/80 flex items-center justify-between bg-white">
          <div>
            <h2 
              id="recent-decisions-heading"
              className="text-xl font-bold text-[#1F2937] tracking-tight font-sans"
            >
              Recent Decisions
            </h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Real-time audit log of automated and team decision workflows
            </p>
          </div>
          <span className="px-3 py-1 text-xs font-semibold bg-slate-100 text-slate-700 rounded-full">
            {decisions.length} total
          </span>
        </div>

        {/* Decisions Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse" role="grid">
            <thead>
              <tr className="border-b border-gray-200 bg-slate-50/60 text-slate-500 text-xs font-bold uppercase tracking-wider">
                <th scope="col" className="py-3.5 px-6 font-semibold">Decision Title</th>
                <th scope="col" className="py-3.5 px-6 font-semibold">Status</th>
                <th scope="col" className="py-3.5 px-6 font-semibold">Confidence</th>
                <th scope="col" className="py-3.5 px-6 font-semibold">Created By</th>
                <th scope="col" className="py-3.5 px-6 font-semibold text-right">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-sm font-medium">
              {decisions.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => handleRowClick(item)}
                  onKeyDown={(e) => handleKeyDown(e, item)}
                  tabIndex={0}
                  role="row"
                  className="
                    group hover:bg-amber-50/40 transition-colors duration-150 cursor-pointer
                    focus:outline-none focus:bg-amber-50/60 focus:ring-2 focus:ring-amber-500/30
                  "
                >
                  {/* Title & Category */}
                  <td className="py-4 px-6 text-slate-900 font-semibold group-hover:text-amber-900 transition-colors">
                    <div className="flex items-center gap-2">
                      <span>{item.title}</span>
                      <ChevronRight className="w-4 h-4 text-slate-300 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
                    </div>
                    {item.category && (
                      <span className="block text-xs font-medium text-slate-400 mt-0.5">
                        {item.category}
                      </span>
                    )}
                  </td>

                  {/* Status Badge */}
                  <td className="py-4 px-6">
                    {getStatusBadge(item.status)}
                  </td>

                  {/* Confidence Meter */}
                  <td className="py-4 px-6 text-slate-700">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-slate-100 rounded-full h-2 overflow-hidden border border-slate-200/60">
                        <div 
                          className={`h-full rounded-full transition-all duration-500 ${
                            item.confidence >= 85 
                              ? 'bg-emerald-500' 
                              : item.confidence >= 70 
                              ? 'bg-amber-500' 
                              : 'bg-rose-500'
                          }`}
                          style={{ width: `${item.confidence}%` }}
                        />
                      </div>
                      <span className="text-xs font-bold text-slate-700 font-mono">
                        {item.confidence}%
                      </span>
                    </div>
                  </td>

                  {/* Owner */}
                  <td className="py-4 px-6 text-slate-700">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-[10px] font-bold">
                        {item.owner.charAt(0)}
                      </div>
                      <span>{item.owner}</span>
                    </div>
                  </td>

                  {/* Date */}
                  <td className="py-4 px-6 text-slate-500 text-right text-xs font-medium font-mono">
                    {item.date}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
