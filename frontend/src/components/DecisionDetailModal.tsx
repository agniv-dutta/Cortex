import React from 'react';
import type { DecisionItem } from '../types/dashboard';
import { X, ShieldCheck, User, Calendar, ArrowUpRight } from 'lucide-react';

interface DecisionDetailModalProps {
  decision: DecisionItem | null;
  onClose: () => void;
}

export const DecisionDetailModal: React.FC<DecisionDetailModalProps> = ({
  decision,
  onClose,
}) => {
  if (!decision) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl border border-gray-200 overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <span className="px-3 py-1 text-xs font-semibold bg-amber-100 text-amber-800 rounded-full">
              {decision.category || 'Decision Intelligence'}
            </span>
            <span className="text-xs text-slate-400 font-mono">ID: {decision.id}</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
            aria-label="Close detail modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6">
          <div>
            <h3 id="modal-title" className="text-xl font-bold text-slate-900 font-sans leading-snug">
              {decision.title}
            </h3>
            {decision.description && (
              <p className="text-sm text-slate-600 mt-2 leading-relaxed">
                {decision.description}
              </p>
            )}
          </div>

          {/* KPI Specs Box */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 rounded-2xl bg-amber-50/50 border border-amber-200/60">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Status</span>
              <span className="text-sm font-bold text-slate-900 mt-0.5 inline-block">
                {decision.status}
              </span>
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Confidence</span>
              <span className="text-sm font-bold text-amber-700 mt-0.5 inline-block">
                {decision.confidence}% Score
              </span>
            </div>
            <div>
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">Impact</span>
              <span className="text-sm font-bold text-emerald-700 mt-0.5 inline-block">
                {decision.impactScore || 'High'}
              </span>
            </div>
          </div>

          {/* Details Metadata */}
          <div className="space-y-3 pt-2 text-xs font-medium text-slate-600 border-t border-gray-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-500">
                <User className="w-4 h-4" />
                <span>Decision Owner</span>
              </div>
              <span className="font-semibold text-slate-900">{decision.owner}</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-500">
                <Calendar className="w-4 h-4" />
                <span>Created Date</span>
              </div>
              <span className="font-mono text-slate-900">{decision.date}</span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-500">
                <ShieldCheck className="w-4 h-4" />
                <span>Verification Engine</span>
              </div>
              <span className="font-semibold text-amber-800">Cortex AI Model v4</span>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-gray-100 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200/80 rounded-xl transition-colors"
          >
            Close
          </button>
          <button
            onClick={() => alert(`Navigating to full report for ${decision.title}`)}
            className="px-4 py-2 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-xl shadow-xs flex items-center gap-1.5 transition-all"
          >
            <span>Full Audit Trail</span>
            <ArrowUpRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
