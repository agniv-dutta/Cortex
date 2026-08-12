import React, { useState, useMemo } from 'react';
import type { 
  PlaybooksBrowserProps, 
  PlaybookItem, 
  PlaybookCategory, 
  PlaybookFilterState 
} from '../types/dashboard';
import { mockPlaybooksData } from '../data/mockData';
import { PlaybookDetailModal } from './PlaybookDetailModal';
import { 
  Filter, 
  RotateCcw, 
  Plus, 
  Handshake, 
  Compass, 
  Layers, 
  Cpu, 
  ArrowRight, 
  ChevronRight,
  BookOpen,
  Search,
  MoreVertical
} from 'lucide-react';

export const PlaybooksBrowser: React.FC<PlaybooksBrowserProps> = ({
  playbooks = mockPlaybooksData,
  onSelectPlaybook,
  onNewPlaybook,
}) => {
  // Filter state
  const [filters, setFilters] = useState<PlaybookFilterState>({
    brand: 'All Brands',
    categories: [],
    lastUpdatedRange: 'Any time',
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPlaybook, setSelectedPlaybook] = useState<PlaybookItem | null>(null);

  // Available Filter Options
  const brandOptions = ['All Brands', 'Brand A', 'Brand B', 'Brand Coffee Co.'];
  const categoryOptions: PlaybookCategory[] = [
    'Vendor Management',
    'Brand Strategy',
    'Product Development',
    'Operations',
  ];

  // Reset Filters
  const handleResetFilters = () => {
    setFilters({
      brand: 'All Brands',
      categories: [],
      lastUpdatedRange: 'Any time',
    });
    setSearchQuery('');
  };

  // Toggle category checkbox
  const toggleCategoryFilter = (cat: PlaybookCategory) => {
    setFilters((prev) => {
      const exists = prev.categories.includes(cat);
      return {
        ...prev,
        categories: exists
          ? prev.categories.filter((c) => c !== cat)
          : [...prev.categories, cat],
      };
    });
  };

  // Filtered Playbooks
  const filteredPlaybooks = useMemo(() => {
    return playbooks.filter((item) => {
      // Search text match
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesText = 
          item.title.toLowerCase().includes(q) ||
          item.description.toLowerCase().includes(q) ||
          item.tags.some((t) => t.toLowerCase().includes(q));
        if (!matchesText) return false;
      }

      // Brand Filter
      if (filters.brand !== 'All Brands') {
        const matchesBrand = item.brands.includes('All Brands') || item.brands.includes(filters.brand);
        if (!matchesBrand) return false;
      }

      // Category Filter
      if (filters.categories.length > 0) {
        if (!filters.categories.includes(item.category)) return false;
      }

      // Last Updated Filter
      if (filters.lastUpdatedRange === 'This week') {
        if (item.lastUpdated.includes('month') || item.lastUpdated.includes('week')) return false;
      }

      return true;
    });
  }, [playbooks, filters, searchQuery]);

  const handleCardClick = (item: PlaybookItem) => {
    setSelectedPlaybook(item);
    if (onSelectPlaybook) {
      onSelectPlaybook(item);
    }
  };

  const getCategoryHeaderStyle = (cat: PlaybookCategory) => {
    switch (cat) {
      case 'Vendor Management':
        return {
          bg: 'bg-[#FFFBEB] border-b border-amber-200/80',
          icon: Handshake,
          iconColor: 'text-amber-700 bg-amber-200/60',
        };
      case 'Brand Strategy':
        return {
          bg: 'bg-[#F0FDF4] border-b border-emerald-200/80',
          icon: Compass,
          iconColor: 'text-emerald-700 bg-emerald-200/60',
        };
      case 'Product Development':
        return {
          bg: 'bg-[#FAF5FF] border-b border-purple-200/80',
          icon: Layers,
          iconColor: 'text-purple-700 bg-purple-200/60',
        };
      case 'Operations':
        return {
          bg: 'bg-[#ECFEFF] border-b border-cyan-200/80',
          icon: Cpu,
          iconColor: 'text-cyan-700 bg-cyan-200/60',
        };
    }
  };

  return (
    <div 
      className="w-full max-w-6xl mx-auto px-4 py-4 space-y-6 font-sans"
      role="region"
      aria-label="Cortex Brand Playbooks and Guidelines"
    >
      {/* 1. Breadcrumbs & Header Bar */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <nav className="flex items-center gap-1.5 text-[11px] font-bold tracking-wider uppercase text-slate-400 mb-1" aria-label="Breadcrumb">
            <span>DASHBOARD</span>
            <ChevronRight className="w-3 h-3 text-slate-300" />
            <span className="text-amber-700">PLAYBOOKS</span>
          </nav>

          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1F2937]">
            Brand Playbooks & Guidelines
          </h1>
          <p className="text-sm font-medium text-slate-500 mt-0.5">
            Centralized source of truth for Think9 operational and strategic decisions
          </p>
        </div>

        {/* Action Button: + New Playbook */}
        <button
          onClick={onNewPlaybook || (() => alert('Creating a new playbook entry...'))}
          className="
            px-4.5 py-2.5 rounded-xl bg-white border border-gray-300 text-slate-800 text-xs sm:text-sm font-bold
            hover:bg-amber-50 hover:border-amber-400 hover:text-amber-800 transition-all duration-200 shadow-xs
            inline-flex items-center gap-2 self-start sm:self-auto active:scale-95 focus:outline-none focus:ring-2 focus:ring-amber-500
          "
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>New Playbook</span>
        </button>
      </header>

      {/* 2. Main Two-Column Layout (Sidebar 240px + Cards Grid) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
        
        {/* Left Filter Sidebar (240px Fixed Width on Desktop) */}
        <aside 
          className="lg:col-span-3 bg-white p-5 rounded-3xl border border-gray-200/90 shadow-xs space-y-6"
          aria-label="Playbook filters"
        >
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
              <Filter className="w-4 h-4 text-amber-600" />
              <span>Filter by</span>
            </div>

            <button
              onClick={handleResetFilters}
              className="text-xs font-semibold text-amber-700 hover:text-amber-900 inline-flex items-center gap-1 hover:underline"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset</span>
            </button>
          </div>

          {/* Search Playbooks Input */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search playbooks..."
              className="w-full pl-9 pr-3 py-2 text-xs font-medium bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:border-amber-500 focus:outline-none"
            />
          </div>

          {/* Section 1: BRAND CONTEXT */}
          <div className="space-y-2.5">
            <h2 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              BRAND CONTEXT
            </h2>
            <div className="space-y-1.5">
              {brandOptions.map((brandName) => {
                const isSelected = filters.brand === brandName;
                return (
                  <label
                    key={brandName}
                    className="flex items-center gap-2.5 text-xs font-semibold text-slate-700 cursor-pointer group hover:text-amber-800"
                  >
                    <input
                      type="radio"
                      name="brandFilter"
                      checked={isSelected}
                      onChange={() => setFilters((prev) => ({ ...prev, brand: brandName }))}
                      className="w-4 h-4 text-amber-600 focus:ring-amber-500 border-gray-300"
                    />
                    <span className={isSelected ? 'text-amber-900 font-bold' : ''}>
                      {brandName}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Section 2: CATEGORY */}
          <div className="space-y-2.5 pt-3 border-t border-gray-100">
            <h2 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              CATEGORY
            </h2>
            <div className="space-y-2">
              {categoryOptions.map((cat) => {
                const isChecked = filters.categories.includes(cat);
                return (
                  <label
                    key={cat}
                    className="flex items-center gap-2.5 text-xs font-semibold text-slate-700 cursor-pointer group hover:text-amber-800"
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleCategoryFilter(cat)}
                      className="w-4 h-4 rounded text-amber-600 focus:ring-amber-500 border-gray-300"
                    />
                    <span className={isChecked ? 'text-amber-900 font-bold' : ''}>
                      {cat}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Section 3: LAST UPDATED */}
          <div className="space-y-2.5 pt-3 border-t border-gray-100">
            <h2 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
              LAST UPDATED
            </h2>
            <select
              value={filters.lastUpdatedRange}
              onChange={(e) => setFilters((prev) => ({ ...prev, lastUpdatedRange: e.target.value as any }))}
              className="w-full text-xs font-semibold text-slate-700 bg-slate-50 border border-slate-200 rounded-xl p-2.5 focus:border-amber-500 focus:outline-none"
            >
              <option value="Any time">Any time</option>
              <option value="This week">This week</option>
              <option value="This month">This month</option>
            </select>
          </div>
        </aside>

        {/* Main Content Grid (2-Column Grid of Playbook Cards) */}
        <main className="lg:col-span-9 space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-500 font-semibold px-1">
            <span>Showing {filteredPlaybooks.length} of {playbooks.length} playbooks</span>
            {filters.categories.length > 0 && (
              <span className="text-amber-800 font-bold">Filtered by {filters.categories.length} category selection</span>
            )}
          </div>

          {filteredPlaybooks.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {filteredPlaybooks.map((item) => {
                const headerStyle = getCategoryHeaderStyle(item.category);
                const Icon = headerStyle.icon;

                return (
                  <article
                    key={item.id}
                    onClick={() => handleCardClick(item)}
                    tabIndex={0}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && handleCardClick(item)}
                    className="
                      bg-white rounded-3xl border border-gray-200/90 shadow-xs overflow-hidden
                      hover:shadow-md hover:-translate-y-1 hover:scale-[1.01] transition-all duration-200
                      cursor-pointer group flex flex-col justify-between focus:outline-none focus:ring-2 focus:ring-amber-500
                    "
                  >
                    {/* Category Tint Header Area */}
                    <div className={`p-5 flex items-center justify-between ${headerStyle.bg}`}>
                      <div className={`p-2.5 rounded-xl ${headerStyle.iconColor} shadow-2xs`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <button 
                        onClick={(e) => { e.stopPropagation(); alert(`Options for ${item.title}`); }}
                        className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-white/60 transition-colors"
                        aria-label="More options"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Card Content Area */}
                    <div className="p-5 flex-1 space-y-3">
                      <h2 className="text-base font-bold text-slate-900 group-hover:text-amber-800 transition-colors font-sans">
                        {item.title}
                      </h2>

                      <p className="text-xs text-slate-600 leading-relaxed line-clamp-2 font-medium">
                        {item.description}
                      </p>

                      {/* Tags Badges */}
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        {item.tags.map((tag, idx) => (
                          <span 
                            key={idx} 
                            className="px-2.5 py-1 text-[11px] font-semibold bg-slate-100 text-slate-700 rounded-lg border border-slate-200/80"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Footer */}
                    <div className="px-5 py-3.5 bg-slate-50/60 border-t border-gray-100 flex items-center justify-between text-[11px] font-mono text-slate-500 font-semibold">
                      <span>LAST UPDATED: {item.lastUpdated.toUpperCase()}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-amber-600 group-hover:translate-x-1 transition-all" />
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            /* No Results Empty State */
            <div className="bg-white rounded-3xl border border-gray-200 p-12 text-center space-y-4 max-w-md mx-auto my-8">
              <div className="w-12 h-12 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mx-auto">
                <BookOpen className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">No playbooks found</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                No playbook documents match your current filter rules. Try resetting your selected brand or category filters.
              </p>
              <button
                onClick={handleResetFilters}
                className="px-5 py-2.5 rounded-xl bg-amber-600 text-white font-bold text-xs hover:bg-amber-700 transition-all shadow-xs"
              >
                Reset All Filters
              </button>
            </div>
          )}
        </main>
      </div>

      {/* Playbook Detail Modal View */}
      <PlaybookDetailModal
        playbook={selectedPlaybook}
        onClose={() => setSelectedPlaybook(null)}
      />
    </div>
  );
};

export default PlaybooksBrowser;
