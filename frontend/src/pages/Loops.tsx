import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play, Pause, Square, Trash2, ChevronDown, ChevronUp,
  RefreshCw, CheckCircle, AlertCircle, Clock, Database
} from 'lucide-react';
import { loops } from '@/data/mock';

const statusConfig: Record<string, { bg: string; text: string; dot: string; icon: React.ElementType }> = {
  running: { bg: 'bg-green-900/40', text: 'text-green-400', dot: 'bg-green-400', icon: RefreshCw },
  paused: { bg: 'bg-amber-900/40', text: 'text-amber-400', dot: 'bg-amber-400', icon: Pause },
  completed: { bg: 'bg-blue-900/40', text: 'text-blue-400', dot: 'bg-blue-400', icon: CheckCircle },
};

export default function Loops() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const stats = {
    total: loops.length,
    running: loops.filter((l) => l.status === 'running').length,
    paused: loops.filter((l) => l.status === 'paused').length,
    completed: loops.filter((l) => l.status === 'completed').length,
  };

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Loops', value: stats.total, color: 'text-text-primary', bg: 'bg-bg-surface' },
          { label: 'Running', value: stats.running, color: 'text-green-400', bg: 'bg-green-900/20' },
          { label: 'Paused', value: stats.paused, color: 'text-amber-400', bg: 'bg-amber-900/20' },
          { label: 'Completed', value: stats.completed, color: 'text-blue-400', bg: 'bg-blue-900/20' },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`${s.bg} border border-border-subtle rounded-card p-4`}
          >
            <p className="text-xs text-text-tertiary">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </motion.div>
        ))}
      </div>

      {/* Loops Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-bg-surface border border-border-subtle rounded-card overflow-hidden"
      >
        <div className="px-5 py-4 border-b border-border-subtle flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Campaign Loops</h2>
          <button className="px-4 py-2 bg-accent-primary text-white text-sm font-medium rounded-lg hover:bg-cyan-500 transition-colors">
            + New Loop
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-text-tertiary border-b border-border-subtle">
                <th className="px-5 py-3 font-medium w-8"></th>
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Iteration</th>
                <th className="px-5 py-3 font-medium">Platforms</th>
                <th className="px-5 py-3 font-medium">Budget</th>
                <th className="px-5 py-3 font-medium">Checkpoint</th>
                <th className="px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loops.map((loop) => {
                const status = statusConfig[loop.status];
                const StatusIcon = status.icon;
                const isExpanded = expandedId === loop.id;

                return (
                  <>
                    <tr
                      key={loop.id}
                      onClick={() => setExpandedId(isExpanded ? null : loop.id)}
                      className="border-b border-border-subtle/50 hover:bg-bg-elevated/50 transition-colors cursor-pointer"
                    >
                      <td className="px-5 py-3.5">
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-text-tertiary" /> : <ChevronDown className="w-4 h-4 text-text-tertiary" />}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="text-sm font-medium text-text-primary">{loop.name}</div>
                        <div className="text-xs text-text-tertiary">{loop.threadId.slice(0, 18)}...</div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${status.bg} ${status.text}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${status.dot} ${loop.status === 'running' ? 'animate-pulse' : ''}`} />
                          <StatusIcon className="w-3 h-3" />
                          {loop.status}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="text-sm text-text-primary">{loop.iteration} / {loop.maxIterations}</div>
                        <div className="w-20 h-1.5 bg-bg-input rounded-full mt-1">
                          <div className="h-full bg-accent-primary rounded-full" style={{ width: `${(loop.iteration / loop.maxIterations) * 100}%` }} />
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex gap-1 flex-wrap">
                          {loop.platforms.map((p) => (
                            <span key={p} className="px-1.5 py-0.5 bg-bg-elevated rounded text-[10px] text-text-secondary border border-border-subtle">
                              {p.replace('_', ' ')}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="text-sm text-text-primary">${loop.budget.toLocaleString()}</div>
                        <div className="text-xs text-text-tertiary">${loop.spend.toLocaleString()} spent</div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-bg-elevated rounded text-xs text-text-secondary border border-border-subtle">
                          <Database className="w-3 h-3" />
                          Memory
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex gap-1">
                          {loop.status === 'paused' && (
                            <button className="p-1.5 rounded-lg text-green-400 hover:bg-green-900/30 transition-colors" title="Resume">
                              <Play className="w-4 h-4" />
                            </button>
                          )}
                          {loop.status === 'running' && (
                            <button className="p-1.5 rounded-lg text-amber-400 hover:bg-amber-900/30 transition-colors" title="Pause">
                              <Pause className="w-4 h-4" />
                            </button>
                          )}
                          <button className="p-1.5 rounded-lg text-text-tertiary hover:text-accent-danger hover:bg-red-900/30 transition-colors" title="Stop">
                            <Square className="w-4 h-4" />
                          </button>
                          <button className="p-1.5 rounded-lg text-text-tertiary hover:text-accent-danger hover:bg-red-900/30 transition-colors" title="Delete">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Expanded Detail */}
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.tr
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <td colSpan={8} className="px-5 py-4 bg-bg-elevated/30">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                              {/* Iteration Timeline */}
                              <div>
                                <p className="text-xs text-text-tertiary mb-2">Iteration History</p>
                                <div className="flex gap-1">
                                  {Array.from({ length: loop.maxIterations }).map((_, i) => (
                                    <div
                                      key={i}
                                      className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                                        i < loop.iteration
                                          ? 'bg-accent-primary text-white'
                                          : 'bg-bg-input text-text-tertiary'
                                      }`}
                                    >
                                      {i + 1}
                                    </div>
                                  ))}
                                </div>
                              </div>

                              {/* State Details */}
                              <div>
                                <p className="text-xs text-text-tertiary mb-2">Current State</p>
                                <div className="space-y-1 text-xs">
                                  <div className="flex justify-between">
                                    <span className="text-text-tertiary">Next Action:</span>
                                    <span className="text-accent-primary">{loop.nextAction}</span>
                                  </div>
                                  <div className="flex justify-between">
                                    <span className="text-text-tertiary">ROAS:</span>
                                    <span className="text-accent-success">{loop.roas}x</span>
                                  </div>
                                </div>
                              </div>

                              {/* Budget Bar */}
                              <div>
                                <p className="text-xs text-text-tertiary mb-2">Budget Usage</p>
                                <div className="h-4 bg-bg-input rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-gradient-to-r from-accent-primary to-accent-secondary rounded-full"
                                    style={{ width: `${Math.min((loop.spend / loop.budget) * 100, 100)}%` }}
                                  />
                                </div>
                                <p className="text-xs text-text-tertiary mt-1">
                                  ${loop.spend.toLocaleString()} / ${loop.budget.toLocaleString()}
                                </p>
                              </div>
                            </div>
                          </td>
                        </motion.tr>
                      )}
                    </AnimatePresence>
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
