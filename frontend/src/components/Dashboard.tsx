import React, { useEffect, useMemo, useState } from 'react';
import type { DashboardProps, NavigationItem, DecisionItem, DecisionBriefData, PlaybookCategory, PlaybookItem } from '../types/dashboard';
import { Sidebar } from './Sidebar';
import { TopNav } from './TopNav';
import { HeroSection } from './HeroSection';
import { StatsCards } from './StatsCards';
import { ActivityFeed } from './ActivityFeed';
import { DecisionDetailModal } from './DecisionDetailModal';
import { DecisionBrief } from './DecisionBrief';
import { AnalyticsDashboard } from './AnalyticsDashboard';
import { PlaybooksBrowser } from './PlaybooksBrowser';
import { 
  mockUserData, 
  mockStatsData, 
  mockRecentQueries, 
  mockDecisions,
  mockDecisionBrief,
  mockPlaybooksData
} from '../data/mockData';

export const Dashboard: React.FC<DashboardProps> = ({
  user = mockUserData,
  recentQueries = mockRecentQueries,
  stats = mockStatsData,
  decisions = mockDecisions,
  activeNav: initialActiveNav = 'dashboard',
  onNavigate,
  onSelectDecision: externalOnSelectDecision,
}) => {
  const [activeNav, setActiveNav] = useState<NavigationItem>(initialActiveNav);
  const [isDarkTheme, setIsDarkTheme] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [selectedDecision, setSelectedDecision] = useState<DecisionItem | null>(null);
  const [showBriefView, setShowBriefView] = useState<boolean>(false);
  const [selectedBrief, setSelectedBrief] = useState<DecisionBriefData | null>(null);
  const [activeSearch, setActiveSearch] = useState<string>('');
  const [playbooksData, setPlaybooksData] = useState<PlaybookItem[]>(mockPlaybooksData);
  const [decisionsData, setDecisionsData] = useState<DecisionItem[]>(decisions);

  useEffect(() => {
    let cancelled = false;

    const loadDecisions = async () => {
      try {
        const response = await fetch('/v1/decisions');
        if (!response.ok) {
          throw new Error(`Decisions fetch failed: ${response.status}`);
        }

        const data = (await response.json()) as DecisionItem[];
        if (!cancelled && data.length > 0) {
          setDecisionsData(data);
        }
      } catch {
        if (!cancelled) {
          setDecisionsData(decisions);
        }
      }
    };

    const loadPlaybooks = async () => {
      try {
        const response = await fetch('/v1/playbooks');
        if (!response.ok) {
          throw new Error(`Playbooks fetch failed: ${response.status}`);
        }

        const data = (await response.json()) as PlaybookItem[];
        if (!cancelled && data.length > 0) {
          setPlaybooksData(data);
        }
      } catch {
        if (!cancelled) {
          setPlaybooksData(mockPlaybooksData);
        }
      }
    };

    void loadDecisions();
    void loadPlaybooks();

    return () => {
      cancelled = true;
    };
  }, [decisions]);

  const playbookFilters = useMemo(() => {
    return {
      brands: Array.from(new Set(playbooksData.flatMap((playbook) => playbook.brands))),
      categories: ['Vendor Management', 'Brand Strategy', 'Product Development', 'Operations'] as PlaybookCategory[],
    };
  }, [playbooksData]);

  const handleNavigation = (path: NavigationItem) => {
    setActiveNav(path);
    if (path === 'decisions') {
      setShowBriefView(true);
    } else {
      setShowBriefView(false);
    }
    if (onNavigate) {
      onNavigate(path);
    }
  };

  const handleSearchSubmit = (query: string) => {
    setActiveSearch(query);
    if (query.toLowerCase().includes('coffee') || query.toLowerCase().includes('vendor')) {
      setShowBriefView(true);
    }
  };

  const handleDecisionSelect = (item: DecisionItem) => {
    setSelectedDecision(item);
    setSelectedBrief({
      id: `brief-${item.id}`,
      decisionId: item.id,
      title: item.title,
      querySubmittedAt: 'Loaded from live decision feed',
      generatedAt: 'Opening live decision brief...',
      recommendation: item.description || 'Loading live recommendation...',
      confidence: item.confidence,
      precedents: [],
      risks: [],
      alternatives: [],
      approvalRequiredFrom: item.category ? [item.category] : [],
      status: item.status,
    });
    setShowBriefView(true);
    if (externalOnSelectDecision) {
      externalOnSelectDecision(item);
    }
  };

  const openFeaturedBrief = () => {
    const item = selectedDecision ?? decisionsData[0];
    if (!item) {
      return;
    }
    handleDecisionSelect(item);
  };

  return (
    <div className="min-h-screen bg-[#F3F4F6] text-[#111827] flex flex-col lg:flex-row font-sans selection:bg-amber-100 selection:text-amber-900">
      {/* 1. Sidebar */}
      <Sidebar
        activeNav={activeNav}
        onNavigate={handleNavigation}
        isDarkTheme={isDarkTheme}
        isOpenMobile={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-x-hidden">
        {/* 2. TopNav */}
        <TopNav
          user={user}
          onSearchSubmit={handleSearchSubmit}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
          isDarkTheme={isDarkTheme}
          onToggleTheme={() => setIsDarkTheme(!isDarkTheme)}
        />

        {/* Dynamic Navigation Content View */}
        <main className="flex-1 py-6 lg:py-10 px-4 sm:px-6 lg:px-8 space-y-4" id="main-content" tabIndex={-1}>
          {showBriefView ? (
            /* Decision Brief Dedicated View */
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-200">
              <DecisionBrief
                brief={selectedBrief ?? mockDecisionBrief}
                onBack={() => setShowBriefView(false)}
                onClose={() => {
                  setShowBriefView(false);
                }}
                onApprove={(metadata) => console.log('Decision Brief Approved', metadata)}
                onRequestInfo={() => console.log('Request info triggered')}
              />
            </div>
          ) : activeNav === 'analytics' ? (
            /* Analytics Overview Module */
            <div className="animate-in fade-in duration-200">
              <AnalyticsDashboard />
            </div>
          ) : activeNav === 'playbooks' ? (
            /* Playbooks Browser Module */
            <div className="animate-in fade-in duration-200">
              <PlaybooksBrowser
                playbooks={playbooksData}
                filters={playbookFilters}
              />
            </div>
          ) : activeNav === 'dashboard' ? (
            <>
              {/* Active Search Notification Banner */}
              {activeSearch && (
                <div className="max-w-6xl mx-auto mb-4">
                  <div className="bg-amber-100/90 border border-amber-300 px-4 py-2.5 rounded-2xl flex items-center justify-between text-amber-900 text-sm font-medium">
                    <span>Active query filter: <strong>"{activeSearch}"</strong></span>
                    <div className="flex items-center gap-3">
                      <button 
                      onClick={openFeaturedBrief}
                      className="text-xs font-bold text-amber-900 bg-amber-200/80 px-2.5 py-1 rounded-lg hover:bg-amber-300 transition-colors"
                    >
                      View Decision Brief &rarr;
                      </button>
                      <button 
                        onClick={() => setActiveSearch('')}
                        className="text-xs text-amber-800 underline hover:text-amber-950 font-bold"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Quick Decision Brief Banner Bar */}
              <div className="max-w-6xl mx-auto mb-2">
                <div className="bg-gradient-to-r from-amber-600 to-amber-700 text-white rounded-2xl p-4 sm:p-5 shadow-md flex items-center justify-between flex-wrap gap-4">
                  <div className="space-y-0.5">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-amber-200">
                      Live Decision Intelligence Brief
                    </span>
                    <h3 className="text-base sm:text-lg font-bold">
                      Vendor Negotiation Decision - Brand Coffee Co.
                    </h3>
                  </div>

                  <button
                    onClick={openFeaturedBrief}
                    className="px-4.5 py-2 rounded-xl bg-white text-amber-800 text-xs sm:text-sm font-bold hover:bg-amber-50 transition-all shadow-xs active:scale-95"
                  >
                    Open Decision Brief &rarr;
                  </button>
                </div>
              </div>

              {/* Hero Search Section */}
              <HeroSection
                recentQueries={recentQueries}
                onSearchSubmit={handleSearchSubmit}
              />

              {/* Stats Cards */}
              <StatsCards stats={stats} />

              {/* Recent Decisions Activity Feed */}
              <ActivityFeed
                decisions={
                  activeSearch 
                    ? decisionsData.filter(d => d.title.toLowerCase().includes(activeSearch.toLowerCase()) || d.category?.toLowerCase().includes(activeSearch.toLowerCase()))
                    : decisionsData
                }
                onSelectDecision={(item) => {
                  handleDecisionSelect(item);
                }}
              />
            </>
          ) : (
            /* Sub-page view for other sidebar links */
            <div className="max-w-6xl mx-auto py-16 text-center">
              <div className="p-12 bg-white rounded-3xl border border-gray-200 shadow-xs max-w-lg mx-auto">
                <span className="inline-block px-4 py-1.5 rounded-full bg-amber-100 text-amber-800 text-xs font-bold uppercase tracking-wider mb-4">
                  {activeNav} Module
                </span>
                <h2 className="text-2xl font-bold text-slate-900 capitalize mb-2">
                  {activeNav} Workspace
                </h2>
                <p className="text-sm text-slate-600 mb-6">
                  You are currently viewing the {activeNav} perspective. Return to the primary dashboard or open Playbooks.
                </p>
                <div className="flex items-center justify-center gap-3">
                  <button
                    onClick={() => handleNavigation('dashboard')}
                    className="px-5 py-2.5 rounded-xl bg-amber-600 text-white font-semibold text-sm hover:bg-amber-700 transition-all shadow-md shadow-amber-600/20"
                  >
                    Back to Dashboard
                  </button>
                  <button
                    onClick={() => handleNavigation('playbooks')}
                    className="px-5 py-2.5 rounded-xl bg-white border border-gray-300 text-slate-700 font-semibold text-sm hover:bg-gray-50 transition-all"
                  >
                    Open Playbooks
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>

        {/* Modal for Decision Detail View */}
        {!showBriefView && (
          <DecisionDetailModal
            decision={selectedDecision}
            onClose={() => setSelectedDecision(null)}
          />
        )}

        {/* Footer */}
        <footer className="w-full py-4 px-8 border-t border-gray-200/60 text-center text-xs text-slate-400 font-medium">
          Cortex Decision Intelligence SaaS &bull; Built with React, TypeScript & Tailwind CSS
        </footer>
      </div>
    </div>
  );
};

export default Dashboard;
