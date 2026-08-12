import React, { useState } from 'react';
import type { 
  DecisionBriefProps, 
  PrecedentItem, 
  RiskItem 
} from '../types/dashboard';
import { mockDecisionBrief } from '../data/mockData';
import { 
  ArrowLeft, 
  X, 
  Lightbulb, 
  CheckCircle2, 
  AlertTriangle, 
  Plus, 
  Minus, 
  Hourglass, 
  ExternalLink
} from 'lucide-react';

export const DecisionBrief: React.FC<DecisionBriefProps> = ({
  brief = mockDecisionBrief,
  onApprove,
  onRequestInfo,
  onBack,
  onClose,
}) => {
  // State for expanded precedent card
  const [expandedPrecedentId, setExpandedPrecedentId] = useState<string | null>(null);
  
  // State for expanded risk mitigation
  const [expandedRiskId, setExpandedRiskId] = useState<string | null>(null);

  // State feedback toast for button actions
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const handleApprove = () => {
    setActionFeedback('Approval submitted successfully!');
    if (onApprove) {
      onApprove();
    }
    setTimeout(() => setActionFeedback(null), 3500);
  };

  const handleRequestInfo = () => {
    setActionFeedback('Information request dispatched to stakeholders.');
    if (onRequestInfo) {
      onRequestInfo();
    }
    setTimeout(() => setActionFeedback(null), 3500);
  };

  const togglePrecedent = (id: string) => {
    setExpandedPrecedentId(prev => prev === id ? null : id);
  };

  const toggleRisk = (id: string) => {
    setExpandedRiskId(prev => prev === id ? null : id);
  };

  const getSeverityBadge = (severity: 'high' | 'medium' | 'low') => {
    switch (severity) {
      case 'high':
        return (
          <span className="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-rose-100 text-rose-700 border border-rose-200">
            High
          </span>
        );
      case 'medium':
        return (
          <span className="px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider rounded-md bg-amber-100 text-amber-800 border border-amber-200">
            Medium
          </span>
        );
      case 'low':
        return (
          <span className="px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider rounded-md bg-slate-100 text-slate-600 border border-slate-200">
            Low
          </span>
        );
    }
  };

  const getDotColor = (index: number) => {
    if (index === 0) return 'bg-amber-500';
    if (index === 1) return 'bg-slate-400';
    return 'bg-emerald-500';
  };

  return (
    <div 
      className="w-full max-w-5xl mx-auto bg-white rounded-3xl border border-gray-200/90 shadow-xl overflow-hidden my-4 lg:my-8 transition-all duration-200 font-sans"
      role="region"
      aria-label="Decision Brief Details"
    >
      {/* Toast Notification Banner */}
      {actionFeedback && (
        <div className="bg-emerald-600 text-white text-sm font-semibold px-6 py-3 flex items-center justify-between shadow-md animate-in slide-in-from-top duration-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5" />
            <span>{actionFeedback}</span>
          </div>
          <button 
            onClick={() => setActionFeedback(null)}
            className="text-white/80 hover:text-white text-xs font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Header Section */}
      <header className="px-6 lg:px-8 py-5 border-b border-gray-200/80 flex items-center justify-between bg-white">
        <div className="flex items-start gap-4">
          {onBack && (
            <button
              onClick={onBack}
              className="p-2 -ml-2 rounded-xl text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
              aria-label="Go Back"
              title="Go Back"
            >
              <ArrowLeft className="w-5 h-5 stroke-[2.5]" />
            </button>
          )}

          <div>
            <h1 className="text-xl lg:text-2xl font-bold tracking-tight text-[#1F2937]">
              {brief.title}
            </h1>
            <p className="text-xs sm:text-sm font-medium text-slate-500 mt-0.5 flex items-center gap-1.5 flex-wrap">
              <span>{brief.querySubmittedAt}</span>
              <span>&bull;</span>
              <span>{brief.generatedAt}</span>
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
            aria-label="Close Decision Brief"
            title="Close Brief"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </header>

      <div className="p-6 lg:p-8 space-y-8">
        {/* 2. Recommendation Box (Amber left border #D97706, warm cream bg #FFFBEB) */}
        <section 
          className="bg-[#FFFBEB] rounded-2xl border border-amber-200/80 border-l-4 border-l-[#D97706] p-6 lg:p-7 shadow-xs relative transition-all duration-200"
          aria-labelledby="recommendation-heading"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-amber-200/60 text-amber-800">
                <Lightbulb className="w-5 h-5 stroke-[2.5]" />
              </div>
              <h2 
                id="recommendation-heading"
                className="text-base font-bold text-slate-900 tracking-tight"
              >
                Recommended Action
              </h2>
            </div>

            {/* Confidence Badge (Top-Right) */}
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100/90 border border-emerald-300 text-emerald-800 text-xs font-bold w-fit">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>{brief.confidence}% Confidence</span>
            </div>
          </div>

          {/* Large Recommendation Text */}
          <p className="text-base sm:text-lg font-semibold text-slate-900 leading-relaxed mb-4">
            {brief.recommendation}
          </p>

          {/* Inner Strategic Note Card */}
          {brief.strategicNote && (
            <div className="bg-white/90 rounded-xl p-4 border border-amber-200/90 text-xs sm:text-sm text-slate-700 leading-relaxed">
              <span className="font-bold text-slate-900">Strategic Note: </span>
              {brief.strategicNote.replace('Strategic Note:', '').trim()}
            </div>
          )}
        </section>

        {/* 3. Two-Column Grid: Precedents + Risks */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
          
          {/* Left Column: 3 Similar Decisions (Historical Precedents) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-[#1F2937] tracking-tight">
                {brief.precedents.length} Similar Decisions
              </h3>
              <span className="text-xs text-slate-400 font-medium">Click to inspect</span>
            </div>

            <div className="space-y-3">
              {brief.precedents.map((item: PrecedentItem, index: number) => {
                const isExpanded = expandedPrecedentId === item.id;
                return (
                  <div
                    key={item.id}
                    onClick={() => togglePrecedent(item.id)}
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && togglePrecedent(item.id)}
                    className="
                      bg-slate-50/70 hover:bg-slate-100/80 border border-gray-200/80 rounded-2xl p-4.5
                      transition-all duration-200 cursor-pointer hover:shadow-sm group
                      focus:outline-none focus:ring-2 focus:ring-amber-500/40
                    "
                    role="button"
                    aria-expanded={isExpanded}
                  >
                    {/* Header line inside card */}
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-2.5 h-2.5 rounded-full ${getDotColor(index)} flex-shrink-0`} />
                        <h4 className="text-sm font-bold text-slate-900 group-hover:text-amber-800 transition-colors">
                          {item.title}
                        </h4>
                      </div>

                      {/* Relevance Score Badge */}
                      <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-bold flex-shrink-0">
                        {item.relevanceScore}% Match
                      </span>
                    </div>

                    {/* Outcome & Key Detail */}
                    <div className="grid grid-cols-2 gap-4 text-xs mt-3 pt-3 border-t border-gray-200/60">
                      <div>
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">
                          Outcome
                        </span>
                        <span className={`font-semibold ${item.outcome.includes('Approved') ? 'text-emerald-700' : 'text-rose-700'}`}>
                          {item.outcome}
                        </span>
                      </div>

                      <div>
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-0.5">
                          Key Detail
                        </span>
                        <span className="font-mono font-medium text-slate-800 bg-white px-2 py-0.5 rounded border border-gray-200 inline-block">
                          {item.keyDetail}
                        </span>
                      </div>
                    </div>

                    {/* Expandable Content */}
                    {isExpanded && item.fullDetails && (
                      <div className="mt-3 pt-3 border-t border-amber-200/60 text-xs text-slate-600 bg-amber-50/50 p-3 rounded-xl animate-in fade-in duration-150">
                        <span className="font-bold text-slate-800 block mb-1">Historical Context:</span>
                        {item.fullDetails}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column: Identified Risks */}
          <div className="lg:col-span-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-[#1F2937] tracking-tight">
                Identified Risks
              </h3>
              <span className="text-xs text-slate-400 font-medium">Click for mitigation</span>
            </div>

            <div className="space-y-3">
              {brief.risks.map((risk: RiskItem) => {
                const isExpanded = expandedRiskId === risk.id;
                return (
                  <div
                    key={risk.id}
                    onClick={() => toggleRisk(risk.id)}
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleRisk(risk.id)}
                    className="
                      bg-white border border-gray-200/90 rounded-2xl p-4.5 transition-all duration-200
                      hover:border-amber-300 hover:shadow-xs cursor-pointer group
                      focus:outline-none focus:ring-2 focus:ring-amber-500/40
                    "
                    role="button"
                    aria-expanded={isExpanded}
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-1.5 rounded-lg bg-amber-50 text-amber-600 mt-0.5 group-hover:scale-110 transition-transform">
                        <AlertTriangle className="w-4 h-4" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 truncate">
                            {risk.type}
                          </span>
                          {getSeverityBadge(risk.severity)}
                        </div>

                        <p className="text-xs sm:text-sm font-medium text-slate-800 leading-snug">
                          {risk.description}
                        </p>

                        {/* Interactive Mitigation Strategy Reveal */}
                        {isExpanded && risk.mitigation && (
                          <div className="mt-3 pt-2.5 border-t border-gray-100 text-xs text-slate-700 bg-slate-50 p-2.5 rounded-xl animate-in fade-in duration-150">
                            <span className="font-bold text-amber-800 block mb-0.5">Mitigation Strategy:</span>
                            {risk.mitigation}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 4. Alternatives Section (De-emphasized) */}
        {brief.alternatives && brief.alternatives.length > 0 && (
          <section className="space-y-3" aria-labelledby="alternatives-heading">
            <h3 
              id="alternatives-heading"
              className="text-base font-bold text-[#1F2937] tracking-tight"
            >
              Other Options Considered
            </h3>

            <div className="bg-slate-50/80 border border-gray-200/90 rounded-2xl p-5 lg:p-6 space-y-4">
              {brief.alternatives.map((alt) => (
                <div key={alt.id} className="space-y-3">
                  <h4 className="text-sm font-bold text-slate-900">
                    {alt.action}
                  </h4>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-medium">
                    {/* Pros */}
                    <div className="space-y-2">
                      <span className="text-[11px] font-bold text-emerald-700 uppercase tracking-wider flex items-center gap-1">
                        <Plus className="w-3.5 h-3.5 stroke-[3]" /> Pros
                      </span>
                      <ul className="space-y-1.5 pl-1">
                        {alt.pros.map((pro, i) => (
                          <li key={i} className="text-slate-700 flex items-start gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 flex-shrink-0" />
                            <span>{pro}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Cons */}
                    <div className="space-y-2">
                      <span className="text-[11px] font-bold text-rose-600 uppercase tracking-wider flex items-center gap-1">
                        <Minus className="w-3.5 h-3.5 stroke-[3]" /> Cons
                      </span>
                      <ul className="space-y-1.5 pl-1">
                        {alt.cons.map((con, i) => (
                          <li key={i} className="text-slate-700 flex items-start gap-2">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 flex-shrink-0" />
                            <span>{con}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 5. Next Steps & Approval Flow Action Footer */}
        <section className="bg-slate-50 border border-gray-200 rounded-2xl p-5 lg:p-6 flex flex-col md:flex-row items-center justify-between gap-5">
          <div className="flex items-center gap-3.5 w-full md:w-auto">
            <div className="p-2.5 rounded-xl bg-white border border-gray-200 text-slate-600 shadow-2xs">
              <Hourglass className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                STATUS
              </span>
              <p className="text-xs sm:text-sm font-semibold text-slate-800">
                Awaiting approval from: {brief.approvalRequiredFrom.join(', ')}
              </p>
            </div>
          </div>

          {/* CTA Action Buttons */}
          <div className="flex items-center gap-3 w-full md:w-auto justify-end">
            <button
              onClick={handleRequestInfo}
              className="
                w-full md:w-auto px-5 py-2.5 rounded-xl text-sm font-semibold text-amber-800 bg-white
                border border-amber-300 hover:bg-amber-50 transition-all duration-200
                focus:outline-none focus:ring-2 focus:ring-amber-500 active:scale-95 shadow-2xs
              "
            >
              Request More Info
            </button>

            <button
              onClick={handleApprove}
              className="
                w-full md:w-auto px-6 py-2.5 rounded-xl text-sm font-bold text-white bg-amber-600
                hover:bg-amber-700 transition-all duration-200 shadow-md shadow-amber-600/25
                focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 active:scale-95
              "
            >
              Approve Recommendation
            </button>
          </div>
        </section>

        {/* 6. Metadata Footer */}
        <footer className="pt-4 border-t border-gray-100 flex items-center justify-between text-xs text-slate-400 font-medium">
          <div>
            <span>Generated by Lens</span>
            <span className="mx-2">&bull;</span>
            <span>Outcome tracking enabled</span>
          </div>

          <a 
            href="#similar-decisions"
            onClick={(e) => { e.preventDefault(); alert('Navigating to full historical decision index'); }}
            className="text-amber-700 hover:text-amber-800 font-semibold inline-flex items-center gap-1 hover:underline"
          >
            <span>View similar decisions</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </footer>
      </div>
    </div>
  );
};

export default DecisionBrief;
