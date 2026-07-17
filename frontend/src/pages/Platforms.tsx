import { useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, Wifi, WifiOff } from 'lucide-react';
import { platforms as allPlatforms } from '@/data/mock';

const filters = ['All', 'MCP', 'API', 'Connected', 'Disconnected'];

export default function Platforms() {
  const [activeFilter, setActiveFilter] = useState('All');

  const filtered = allPlatforms.filter((p) => {
    if (activeFilter === 'All') return true;
    if (activeFilter === 'MCP') return p.type === 'mcp';
    if (activeFilter === 'API') return p.type === 'api';
    if (activeFilter === 'Connected') return p.status === 'connected';
    if (activeFilter === 'Disconnected') return p.status === 'disconnected';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Filter Bar */}
      <div className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f}
            onClick={() => setActiveFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeFilter === f
                ? 'bg-accent-primary text-white'
                : 'bg-bg-surface text-text-secondary border border-border-subtle hover:bg-bg-elevated'
            }`}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-sm text-text-tertiary self-center">
          {filtered.length} platforms
        </span>
      </div>

      {/* Platform Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.map((platform, i) => (
          <motion.div
            key={platform.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.35 }}
            className={`bg-bg-surface border rounded-card p-5 hover:border-border-active hover:shadow-lg transition-all ${
              platform.type === 'mcp' ? 'border-l-4 border-l-accent-secondary' : 'border-l-4 border-l-text-tertiary'
            }`}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-text-primary">{platform.displayName}</h3>
                <div className="flex gap-2 mt-1.5">
                  {/* Status */}
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${
                    platform.status === 'connected'
                      ? 'bg-green-900/40 text-green-400 border-green-800'
                      : 'bg-red-900/40 text-red-400 border-red-800'
                  }`}>
                    {platform.status === 'connected' ? (
                      <><Wifi className="w-3 h-3" /> Connected</>
                    ) : (
                      <><WifiOff className="w-3 h-3" /> Disconnected</>
                    )}
                  </span>
                  {/* Type */}
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                    platform.type === 'mcp'
                      ? 'bg-purple-900/40 text-purple-400 border-purple-800'
                      : 'bg-bg-elevated text-text-tertiary border-border-subtle'
                  }`}>
                    {platform.type === 'mcp' ? 'MCP' : 'API'}
                  </span>
                </div>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-bg-elevated rounded-lg p-3">
                <p className="text-xs text-text-tertiary">Avg CPM</p>
                <p className="text-sm font-semibold text-text-primary">${platform.avgCpm}</p>
              </div>
              <div className="bg-bg-elevated rounded-lg p-3">
                <p className="text-xs text-text-tertiary">Avg CPC</p>
                <p className="text-sm font-semibold text-text-primary">${platform.avgCpc}</p>
              </div>
              <div className="bg-bg-elevated rounded-lg p-3">
                <p className="text-xs text-text-tertiary">Min Budget</p>
                <p className="text-sm font-semibold text-text-primary">${platform.minBudget}</p>
              </div>
            </div>

            {/* Objectives */}
            <div className="mb-3">
              <p className="text-xs text-text-tertiary mb-1.5">Objectives</p>
              <div className="flex flex-wrap gap-1">
                {platform.objectives.map((obj) => (
                  <span key={obj} className="px-2 py-0.5 bg-accent-primary-dim text-accent-primary rounded text-xs">
                    {obj}
                  </span>
                ))}
              </div>
            </div>

            {/* Capabilities */}
            <div className="mb-4">
              <p className="text-xs text-text-tertiary mb-1.5">Capabilities</p>
              <div className="flex flex-wrap gap-1">
                {platform.capabilities.map((cap) => (
                  <span key={cap} className="px-2 py-0.5 bg-bg-elevated text-text-secondary rounded text-xs border border-border-subtle">
                    {cap}
                  </span>
                ))}
              </div>
            </div>

            {/* Action */}
            <button className="w-full py-2 border border-border-subtle text-text-secondary rounded-lg text-sm hover:border-accent-primary hover:text-accent-primary transition-colors flex items-center justify-center gap-2">
              <Settings className="w-4 h-4" />
              Configure
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
