import { useLocation } from 'react-router-dom';
import { Bell } from 'lucide-react';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/platforms': 'Platforms',
  '/think': 'Agent Thinking',
  '/loops': 'Loop Monitor',
  '/campaigns': 'Campaigns',
};

export default function Navbar() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'AdCast Console';

  return (
    <header className="fixed top-0 right-0 left-[240px] h-16 bg-bg-surface/80 backdrop-blur-md border-b border-border-subtle z-30 flex items-center justify-between px-6">
      <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
      <div className="flex items-center gap-4">
        <button className="relative p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-elevated transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-accent-danger rounded-full" />
        </button>
        <div className="w-8 h-8 rounded-full bg-accent-primary-dim flex items-center justify-center text-accent-primary text-sm font-bold">
          AD
        </div>
      </div>
    </header>
  );
}
