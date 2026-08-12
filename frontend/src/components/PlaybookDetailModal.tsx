import React, { useState } from 'react';
import type { PlaybookItem } from '../types/dashboard';
import { 
  X, 
  Download, 
  Share2, 
  Printer, 
  BookOpen, 
  ChevronDown, 
  ChevronRight,
  Clock,
  Tag,
  CheckCircle2
} from 'lucide-react';

interface PlaybookDetailModalProps {
  playbook: PlaybookItem | null;
  onClose: () => void;
}

export const PlaybookDetailModal: React.FC<PlaybookDetailModalProps> = ({
  playbook,
  onClose,
}) => {
  const [openSectionIds, setOpenSectionIds] = useState<string[]>([]);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  if (!playbook) return null;

  // Toggle collapsible section accordion
  const toggleSection = (id: string) => {
    setOpenSectionIds((prev) => 
      prev.includes(id) ? prev.filter(sId => sId !== id) : [...prev, id]
    );
  };

  const handleAction = (actionName: string) => {
    setActionFeedback(`${actionName} action triggered for "${playbook.title}".`);
    setTimeout(() => setActionFeedback(null), 3000);
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="playbook-modal-title"
    >
      <div className="bg-white w-full max-w-3xl rounded-3xl shadow-2xl border border-gray-200 overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200">
        
        {/* Toast Action Feedback Banner */}
        {actionFeedback && (
          <div className="bg-amber-600 text-white text-xs font-semibold px-6 py-2.5 flex items-center justify-between shadow-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>{actionFeedback}</span>
            </div>
            <button onClick={() => setActionFeedback(null)} className="text-white/80 hover:text-white">
              Dismiss
            </button>
          </div>
        )}

        {/* Modal Header */}
        <div className="px-6 lg:px-8 py-5 border-b border-gray-200/80 flex items-start justify-between bg-slate-50/50">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-1 text-xs font-bold bg-amber-100 text-amber-800 rounded-full">
                {playbook.category}
              </span>
              {playbook.brands.map((b, i) => (
                <span key={i} className="px-2.5 py-0.5 text-xs font-semibold bg-slate-200 text-slate-700 rounded-md">
                  {b}
                </span>
              ))}
            </div>

            <h2 id="playbook-modal-title" className="text-xl lg:text-2xl font-bold text-slate-900 font-sans tracking-tight">
              {playbook.title}
            </h2>
            <p className="text-xs text-slate-500 font-medium flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              <span>Last updated: {playbook.lastUpdated}</span>
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
            aria-label="Close playbook modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body / Collapsible Sections */}
        <div className="p-6 lg:p-8 overflow-y-auto space-y-6 flex-1">
          {/* Overview Description */}
          <div className="bg-amber-50/60 border border-amber-200/70 p-4.5 rounded-2xl">
            <h3 className="text-xs font-bold uppercase tracking-wider text-amber-900 mb-1 flex items-center gap-1.5">
              <BookOpen className="w-4 h-4 text-amber-600" /> Executive Overview
            </h3>
            <p className="text-sm text-slate-700 leading-relaxed font-medium">
              {playbook.description}
            </p>
          </div>

          {/* Tags */}
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <Tag className="w-3.5 h-3.5 text-slate-400" />
            <span className="font-semibold text-slate-500">Keywords:</span>
            {playbook.tags.map((tag, idx) => (
              <span key={idx} className="px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 font-medium border border-slate-200">
                #{tag}
              </span>
            ))}
          </div>

          {/* Collapsible Sections */}
          <div className="space-y-4 pt-2">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">
              Playbook Guidelines & Sections
            </h3>

            {playbook.sections && playbook.sections.length > 0 ? (
              playbook.sections.map((sec) => {
                const isOpen = openSectionIds.includes(sec.id) || openSectionIds.length === 0; // Default open first
                return (
                  <div key={sec.id} className="border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-2xs">
                    <button
                      onClick={() => toggleSection(sec.id)}
                      className="w-full px-5 py-4 flex items-center justify-between text-left bg-slate-50/70 hover:bg-amber-50/50 transition-colors font-bold text-slate-900 text-sm"
                    >
                      <span>{sec.title}</span>
                      {isOpen ? (
                        <ChevronDown className="w-4 h-4 text-amber-600" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}
                    </button>

                    {isOpen && (
                      <div className="p-5 border-t border-gray-100 text-xs sm:text-sm text-slate-700 leading-relaxed space-y-3 bg-white">
                        <p>{sec.content}</p>

                        {sec.subsections && sec.subsections.length > 0 && (
                          <div className="mt-3 space-y-2 pt-2 border-t border-slate-100">
                            {sec.subsections.map((sub, i) => (
                              <div key={i} className="bg-slate-50 p-3 rounded-xl border border-slate-200/60">
                                <span className="font-bold text-slate-900 block mb-0.5">{sub.title}</span>
                                <span className="text-slate-600 text-xs">{sub.content}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-slate-500 italic">No formal section breakdowns attached.</p>
            )}
          </div>
        </div>

        {/* Modal Action Bar Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-gray-200/80 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs text-slate-400 font-medium">Cortex Knowledge System v2.4</span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleAction('Download PDF')}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-white border border-gray-300 hover:bg-gray-100 transition-colors inline-flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download PDF</span>
            </button>

            <button
              onClick={() => handleAction('Share')}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-white border border-gray-300 hover:bg-gray-100 transition-colors inline-flex items-center gap-1.5"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>Share</span>
            </button>

            <button
              onClick={() => handleAction('Print')}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-700 bg-white border border-gray-300 hover:bg-gray-100 transition-colors inline-flex items-center gap-1.5"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print</span>
            </button>

            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 transition-colors ml-2"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
