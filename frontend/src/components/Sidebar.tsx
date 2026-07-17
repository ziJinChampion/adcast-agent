import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard, Globe, Brain, RefreshCw, Target,
  Zap, LogOut, ChevronLeft, ChevronRight
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useState } from 'react';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Globe, label: 'Platforms', path: '/platforms' },
  { icon: Brain, label: 'Think', path: '/think' },
  { icon: RefreshCw, label: 'Loops', path: '/loops' },
  { icon: Target, label: 'Campaigns', path: '/campaigns' },
];

export default function Sidebar() {
  const { logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <motion.aside
      initial={{ x: -240 }}
      animate={{ x: 0, width: collapsed ? 64 : 240 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="fixed left-0 top-0 h-screen bg-bg-surface border-r border-border-subtle z-40 flex flex-col"
    >
      {/* Brand */}
      <div className="h-16 flex items-center px-4 border-b border-border-subtle">
        <Zap className="w-7 h-7 text-accent-primary flex-shrink-0" />
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="ml-3 overflow-hidden"
          >
            <div className="text-lg font-bold text-text-primary leading-tight">AdCast</div>
            <div className="text-xs text-accent-primary leading-tight">Console</div>
          </motion.div>
        )}
      </div>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-bg-elevated border border-border-subtle rounded-full flex items-center justify-center text-text-tertiary hover:text-text-primary transition-colors z-50"
      >
        {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
      </button>

      {/* Nav Items */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-accent-primary-dim text-accent-primary border-l-2 border-accent-primary'
                  : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
              }`
            }
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {!collapsed && (
              <span className="text-sm font-medium whitespace-nowrap">{item.label}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User Section */}
      <div className="p-3 border-t border-border-subtle">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-accent-primary-dim flex items-center justify-center text-accent-primary text-sm font-bold flex-shrink-0">
            AD
          </div>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text-primary truncate">Admin</div>
              <div className="text-xs text-text-tertiary truncate">admin@adcast.ai</div>
            </div>
          )}
          {!collapsed && (
            <button
              onClick={logout}
              className="p-1.5 rounded-lg text-text-tertiary hover:text-accent-danger hover:bg-bg-elevated transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </motion.aside>
  );
}
