import React, { useState, useRef, useEffect } from 'react';
import { 
  Search, 
  HelpCircle, 
  Settings, 
  Menu, 
  User, 
  LogOut, 
  Moon, 
  Sun,
  Bell
} from 'lucide-react';
import type { TopNavProps } from '../types/dashboard';

export const TopNav: React.FC<TopNavProps> = ({
  user = {
    name: 'Sarah Jenkins',
    email: 'sarah.j@cortex.ai',
    role: 'COO',
    avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256'
  },
  onSearchSubmit,
  onToggleMobileSidebar,
  isDarkTheme = false,
  onToggleTheme,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim() && onSearchSubmit) {
      onSearchSubmit(searchQuery.trim());
    }
  };

  return (
    <header 
      className="w-full h-[80px] lg:h-[90px] px-4 lg:px-8 bg-white border-b border-gray-200/80 flex items-center justify-between sticky top-0 z-30 shadow-xs"
      role="banner"
    >
      {/* Mobile Hamburger & Brand Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleMobileSidebar}
          className="lg:hidden p-2 rounded-xl text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
          aria-label="Open Mobile Menu Navigation"
        >
          <Menu className="w-6 h-6" />
        </button>

        {/* Global Search Bar (Focus State: Border in Amber, Light Amber BG) */}
        <form 
          onSubmit={handleSearchSubmit} 
          className="relative hidden sm:block w-72 md:w-96"
          role="search"
        >
          <label htmlFor="top-search-input" className="sr-only">Search queries and decisions</label>
          <div className="relative group">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-amber-600 transition-colors pointer-events-none" />
            <input
              id="top-search-input"
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="
                w-full pl-10 pr-4 py-2.5 rounded-xl text-sm font-medium text-slate-800 bg-slate-100/80 border border-transparent
                placeholder:text-slate-400 transition-all duration-200
                focus:bg-amber-50/60 focus:border-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500/20
              "
            />
          </div>
        </form>
      </div>

      {/* Right Quick Controls & Profile Dropdown */}
      <div className="flex items-center gap-2 lg:gap-3.5">
        {/* Theme Mode Switcher */}
        {onToggleTheme && (
          <button
            onClick={onToggleTheme}
            className="p-2.5 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
            aria-label={`Switch to ${isDarkTheme ? 'Light Sidebar' : 'Dark Slate Sidebar'}`}
            title={`Toggle Theme (${isDarkTheme ? 'Dark' : 'Light'})`}
          >
            {isDarkTheme ? <Sun className="w-5 h-5 text-amber-500" /> : <Moon className="w-5 h-5 text-slate-600" />}
          </button>
        )}

        {/* Help Center Icon */}
        <button
          className="p-2.5 rounded-xl text-slate-500 hover:text-amber-700 hover:bg-amber-50 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
          aria-label="Help and Documentation"
          title="Help & Support"
        >
          <HelpCircle className="w-5 h-5" />
        </button>

        {/* Notification Bell */}
        <button
          className="relative p-2.5 rounded-xl text-slate-500 hover:text-amber-700 hover:bg-amber-50 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
          aria-label="Notifications"
          title="System Alerts"
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-amber-600 ring-2 ring-white" />
        </button>

        {/* Quick Settings Icon */}
        <button
          className="p-2.5 rounded-xl text-slate-500 hover:text-amber-700 hover:bg-amber-50 transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500"
          aria-label="System Settings"
          title="System Settings"
        >
          <Settings className="w-5 h-5" />
        </button>

        {/* User Profile Menu */}
        <div className="relative ml-2" ref={dropdownRef}>
          <button
            onClick={() => setIsProfileOpen(!isProfileOpen)}
            className="flex items-center gap-3 p-1 rounded-full hover:ring-2 hover:ring-amber-500/40 transition-all focus:outline-none focus:ring-2 focus:ring-amber-500"
            aria-expanded={isProfileOpen}
            aria-haspopup="true"
            aria-label="User profile menu"
          >
            {user.avatarUrl ? (
              <img
                src={user.avatarUrl}
                alt={user.name}
                className="w-10 h-10 rounded-full object-cover border border-amber-500/30 shadow-xs"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-amber-600 text-white flex items-center justify-center font-bold text-sm">
                {user.name.charAt(0)}
              </div>
            )}
          </button>

          {/* Profile Dropdown Popup */}
          {isProfileOpen && (
            <div 
              className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150"
              role="menu"
              aria-orientation="vertical"
            >
              <div className="px-4 py-3 border-b border-gray-100">
                <p className="text-sm font-bold text-slate-900">{user.name}</p>
                <p className="text-xs text-slate-500 font-medium truncate">{user.email}</p>
                <span className="inline-block mt-1.5 px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-800 rounded-md">
                  {user.role}
                </span>
              </div>

              <div className="py-1">
                <button
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-amber-50 hover:text-amber-700 transition-colors"
                  role="menuitem"
                  onClick={() => setIsProfileOpen(false)}
                >
                  <User className="w-4 h-4 text-slate-400" />
                  <span>Profile Settings</span>
                </button>
                <button
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-amber-50 hover:text-amber-700 transition-colors"
                  role="menuitem"
                  onClick={() => setIsProfileOpen(false)}
                >
                  <Settings className="w-4 h-4 text-slate-400" />
                  <span>Account Preferences</span>
                </button>
              </div>

              <div className="pt-1 border-t border-gray-100">
                <button
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-sm font-semibold text-rose-600 hover:bg-rose-50 transition-colors"
                  role="menuitem"
                  onClick={() => setIsProfileOpen(false)}
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
