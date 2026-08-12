import React from 'react';
import { 
  LayoutGrid, 
  GitPullRequest, 
  BookOpen, 
  Store, 
  BarChart3, 
  Settings, 
  X,
  Zap
} from 'lucide-react';
import type { SidebarProps, NavigationItem } from '../types/dashboard';
import { colors } from '../theme/colors';

interface NavConfigItem {
  id: NavigationItem;
  label: string;
  icon: React.ElementType;
}

const navItems: NavConfigItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutGrid },
  { id: 'decisions', label: 'Decisions', icon: GitPullRequest },
  { id: 'playbooks', label: 'Playbooks', icon: BookOpen },
  { id: 'vendors', label: 'Vendors', icon: Store },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeNav = 'dashboard',
  onNavigate,
  isDarkTheme = false, // default light to match Stitch visual frame, toggleable to dark slate
  isOpenMobile = false,
  onCloseMobile,
}) => {
  const handleItemClick = (id: NavigationItem) => {
    if (onNavigate) {
      onNavigate(id);
    }
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  // Base background style based on theme choice (Dark Slate #1F2937 vs White/Light per mockup)
  const bgClass = isDarkTheme 
    ? 'bg-[#1F2937] text-slate-100 border-r border-slate-700' 
    : 'bg-white text-slate-800 border-r border-gray-200';

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpenMobile && (
        <div 
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        id="main-sidebar"
        role="navigation"
        aria-label="Main Navigation"
        className={`
          fixed top-0 bottom-0 left-0 z-50 w-[240px] flex flex-col justify-between p-5 transition-transform duration-300 ease-in-out
          ${bgClass}
          lg:translate-x-0 lg:static
          ${isOpenMobile ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Top Header & Brand */}
        <div>
          <div className="flex items-center justify-between mb-8 px-2">
            <div className="flex items-center gap-2.5 cursor-pointer">
              <div 
                className="w-9 h-9 rounded-xl flex items-center justify-center shadow-md transition-transform hover:scale-105"
                style={{ backgroundColor: colors.amber[600] }}
              >
                <Zap className="w-5 h-5 text-white stroke-[2.5]" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight font-sans" style={{ color: isDarkTheme ? '#FFFFFF' : colors.text.primary }}>
                  Cortex
                </h1>
                <p className="text-[11px] font-medium tracking-wide uppercase" style={{ color: isDarkTheme ? '#94A3B8' : colors.text.muted }}>
                  Decision Intelligence
                </p>
              </div>
            </div>

            {/* Mobile Close Button */}
            <button
              onClick={onCloseMobile}
              className="lg:hidden p-1.5 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              aria-label="Close Sidebar Menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="space-y-1.5" aria-label="Sidebar Primary Navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeNav === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item.id)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`
                    w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 group focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1
                    ${
                      isActive
                        ? 'bg-amber-600 text-white shadow-md shadow-amber-600/20 translate-x-1'
                        : isDarkTheme
                        ? 'text-slate-300 hover:bg-slate-800 hover:text-white hover:translate-x-0.5'
                        : 'text-slate-700 hover:bg-amber-50 hover:text-amber-700 hover:translate-x-0.5'
                    }
                  `}
                >
                  <Icon 
                    className={`w-5 h-5 transition-transform duration-200 group-hover:scale-110 ${
                      isActive 
                        ? 'text-white' 
                        : isDarkTheme 
                        ? 'text-slate-400 group-hover:text-amber-400' 
                        : 'text-slate-500 group-hover:text-amber-600'
                    }`} 
                  />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Footer / Settings Link */}
        <div className="pt-4 border-t border-slate-200/20">
          <button
            onClick={() => handleItemClick('settings')}
            aria-current={activeNav === 'settings' ? 'page' : undefined}
            className={`
              w-full flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 group focus:outline-none focus:ring-2 focus:ring-amber-500
              ${
                activeNav === 'settings'
                  ? 'bg-amber-600 text-white shadow-md shadow-amber-600/20'
                  : isDarkTheme
                  ? 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  : 'text-slate-700 hover:bg-amber-50 hover:text-amber-700'
              }
            `}
          >
            <Settings 
              className={`w-5 h-5 transition-transform duration-200 group-hover:rotate-45 ${
                activeNav === 'settings'
                  ? 'text-white'
                  : isDarkTheme
                  ? 'text-slate-400 group-hover:text-amber-400'
                  : 'text-slate-500 group-hover:text-amber-600'
              }`} 
            />
            <span>Settings</span>
          </button>
        </div>
      </aside>
    </>
  );
};
