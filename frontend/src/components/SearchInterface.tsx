import React, { useState, useEffect, useRef } from 'react';
import type { 
  SearchInterfaceProps, 
  QueryDetectionInfo, 
  QueryTemplateItem, 
  RecentSearchItem 
} from '../types/dashboard';
import { 
  mockSearchTemplates, 
  mockRecentSearchItems 
} from '../data/mockData';
import { 
  Search, 
  ArrowRight, 
  Sparkles, 
  Clock, 
  Building2, 
  Zap, 
  X, 
  Command, 
  History, 
  FileText,
  CheckCircle2
} from 'lucide-react';

export const SearchInterface: React.FC<SearchInterfaceProps> = ({
  onSubmitQuery,
  recentQueries = mockRecentSearchItems,
  templates = mockSearchTemplates,
  placeholder = 'Ask a question or describe a decision scenario...',
  initialQuery = '',
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Real-time heuristic query assistant detector
  const detectQueryMetadata = (text: string): QueryDetectionInfo => {
    const lower = text.toLowerCase();
    
    let category: QueryDetectionInfo['category'] = 'General';
    if (lower.includes('moq') || lower.includes('vendor') || lower.includes('supplier') || lower.includes('procure') || lower.includes('contract')) {
      category = 'Procurement';
    } else if (lower.includes('budget') || lower.includes('strategy') || lower.includes('marketing') || lower.includes('reallocat') || lower.includes('roi')) {
      category = 'Strategy';
    } else if (lower.includes('facility') || lower.includes('logistics') || lower.includes('eu') || lower.includes('tariff') || lower.includes('ship')) {
      category = 'Supply Chain';
    } else if (lower.includes('saas') || lower.includes('telemetry') || lower.includes('license') || lower.includes('app') || lower.includes('feature')) {
      category = 'Product';
    }

    // Brands count estimation
    let brandsAffected = 1;
    if (lower.includes('all') || lower.includes('portfolio') || lower.includes('global')) {
      brandsAffected = 5;
    } else if (lower.includes('coffee') || lower.includes('brand x') || lower.includes('multi')) {
      brandsAffected = 3;
    } else if (text.length > 25) {
      brandsAffected = 2;
    }

    // Response time estimation
    const timeEst = Math.max(1.1, +(1.1 + text.length * 0.02).toFixed(1));
    const estimatedTime = `${timeEst}s`;

    return { category, brandsAffected, estimatedTime };
  };

  const detection = query.trim() ? detectQueryMetadata(query) : null;

  // Global Cmd+K / Ctrl+K keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && onSubmitQuery) {
      const info = detectQueryMetadata(query);
      onSubmitQuery({
        query: query.trim(),
        category: info.category,
        detection: info,
      });
    }
  };

  const handleTemplateClick = (tmpl: QueryTemplateItem) => {
    setQuery(tmpl.defaultQuery);
    setSelectedTemplateId(tmpl.id);
    inputRef.current?.focus();
  };

  const handleRecentClick = (item: RecentSearchItem) => {
    setQuery(item.query);
    if (onSubmitQuery) {
      const info = detectQueryMetadata(item.query);
      onSubmitQuery({
        query: item.query,
        category: info.category,
        detection: info,
      });
    }
  };

  const handleKeyDownInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setQuery('');
      setSelectedTemplateId(null);
    }
  };

  return (
    <section 
      className="w-full max-w-5xl mx-auto my-6 p-6 sm:p-8 lg:p-10 rounded-3xl bg-gradient-to-b from-[#1F2937] to-[#374151] text-white shadow-2xl border border-slate-700/60 font-sans"
      aria-label="Cortex Decision Intelligence Search"
    >
      {/* Header Section */}
      <div className="text-center max-w-2xl mx-auto mb-8">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold mb-4 backdrop-blur-xs">
          <Sparkles className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
          <span>Institutional Query Engine</span>
        </div>

        <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight text-white font-sans leading-tight">
          What decision do you need to make today?
        </h2>
        <p className="text-sm sm:text-base font-medium text-slate-300 mt-2">
          Ask a natural language query or pick a decision template below
        </p>
      </div>

      {/* Controlled Search Form */}
      <form 
        onSubmit={handleSubmit}
        className="w-full max-w-3xl mx-auto mb-6 relative group"
        role="search"
      >
        <div className="relative flex items-center">
          <Search className="w-5 h-5 absolute left-5 text-slate-400 group-focus-within:text-amber-500 transition-colors pointer-events-none" />

          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (selectedTemplateId) setSelectedTemplateId(null);
            }}
            onKeyDown={handleKeyDownInput}
            placeholder={placeholder}
            className="
              w-full pl-13 pr-28 py-4 sm:py-4.5 text-base font-medium text-[#111827] bg-white rounded-2xl
              border-2 border-gray-200 placeholder:text-slate-400 transition-all duration-200
              hover:border-slate-300
              focus:border-[#D97706] focus:outline-none focus:ring-4 focus:ring-[#D97706]/20 focus:shadow-amber-glow
            "
            aria-label="Search decision queries"
          />

          {/* Clear button if text exists */}
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              className="absolute right-14 p-1.5 rounded-full text-slate-400 hover:text-slate-600 transition-colors"
              aria-label="Clear input"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          {/* Submit Arrow Button */}
          <button
            type="submit"
            className="
              absolute right-3 p-2.5 rounded-xl bg-[#D97706] hover:bg-amber-700 text-white
              shadow-md shadow-amber-900/30 transition-all duration-200 hover:scale-105 active:scale-95
              focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-slate-800
            "
            aria-label="Execute Decision Query"
          >
            <ArrowRight className="w-5 h-5 stroke-[2.5]" />
          </button>
        </div>

        {/* Real-time Query Assistant HUD Banner */}
        {detection && (
          <div className="mt-3 bg-slate-800/90 border border-amber-500/30 rounded-2xl p-3.5 px-5 backdrop-blur-xs flex items-center justify-between text-xs text-amber-300 animate-in fade-in duration-150 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400 animate-bounce" />
              <span className="font-bold text-white">Assistant Prediction:</span>
              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold border border-amber-500/40">
                {detection.category} Category
              </span>
            </div>

            <div className="flex items-center gap-4 text-slate-300 font-medium">
              <span className="flex items-center gap-1">
                <Building2 className="w-3.5 h-3.5 text-amber-400" />
                <strong className="text-white">{detection.brandsAffected}</strong> Brand{detection.brandsAffected > 1 ? 's' : ''} Affected
              </span>
              <span className="flex items-center gap-1 font-mono">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                Est. <strong className="text-white">{detection.estimatedTime}</strong>
              </span>
            </div>
          </div>
        )}
      </form>

      {/* 4 Quick Template Buttons */}
      <div className="w-full max-w-3xl mx-auto mb-8 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-amber-400" />
            Quick Decision Templates
          </span>
          <span className="text-[11px] text-slate-500">Click to pre-fill</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {templates.map((tmpl) => {
            const isSelected = selectedTemplateId === tmpl.id;
            return (
              <button
                key={tmpl.id}
                type="button"
                onClick={() => handleTemplateClick(tmpl)}
                className={`
                  p-3.5 rounded-2xl text-left border text-xs font-semibold transition-all duration-200 flex flex-col justify-between group
                  focus:outline-none focus:ring-2 focus:ring-amber-500
                  ${
                    isSelected
                      ? 'bg-[#D97706] border-[#D97706] text-white shadow-md shadow-amber-900/40 translate-y-[-2px]'
                      : 'border-amber-500/50 text-amber-300 bg-slate-800/40 hover:bg-[#D97706] hover:border-[#D97706] hover:text-white'
                  }
                `}
              >
                <div>
                  <span className="block font-bold text-sm mb-1 group-hover:text-white">
                    {tmpl.label}
                  </span>
                  <p className={`text-[11px] font-normal line-clamp-2 ${isSelected ? 'text-amber-100' : 'text-slate-400 group-hover:text-amber-100'}`}>
                    {tmpl.description}
                  </p>
                </div>
                <span className={`text-[10px] mt-2.5 font-semibold self-end uppercase ${isSelected ? 'text-white' : 'text-amber-400 group-hover:text-white'}`}>
                  Preset &rarr;
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Recent Searches List */}
      {recentQueries && recentQueries.length > 0 && (
        <div className="w-full max-w-3xl mx-auto pt-6 border-t border-slate-700/80">
          <div className="flex items-center justify-between mb-3 text-xs">
            <span className="font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <History className="w-3.5 h-3.5 text-amber-400" />
              Recent Searches
            </span>
            <span className="text-[11px] text-slate-500 flex items-center gap-1 font-mono">
              <Command className="w-3 h-3 text-slate-400" /> + K to focus search
            </span>
          </div>

          <div className="space-y-2">
            {recentQueries.map((item) => (
              <div
                key={item.id}
                onClick={() => handleRecentClick(item)}
                tabIndex={0}
                onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleRecentClick(item)}
                className="
                  flex items-center justify-between p-2.5 px-4 rounded-xl bg-slate-800/50 hover:bg-slate-700/60
                  border border-slate-700/40 transition-colors duration-150 cursor-pointer group
                  focus:outline-none focus:ring-2 focus:ring-amber-500
                "
                role="button"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Clock className="w-3.5 h-3.5 text-slate-400 group-hover:text-amber-400 transition-colors flex-shrink-0" />
                  <span className="text-xs font-medium text-slate-200 group-hover:text-white group-hover:underline truncate">
                    {item.query}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono flex-shrink-0">
                  {item.duration && <span>{item.duration}</span>}
                  <span>&bull;</span>
                  <span>{item.timestamp}</span>
                  {item.status === 'Approved' && (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 ml-1" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};

export default SearchInterface;
