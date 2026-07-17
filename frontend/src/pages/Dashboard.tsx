import { motion } from 'framer-motion';
import {
  Target, RefreshCw, DollarSign, TrendingUp,
  Play, Pause, AlertTriangle
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip
} from 'recharts';
import { loops, campaigns, activityFeed, kpiData, donutData } from '@/data/mock';

const kpiCards = [
  { label: 'Total Campaigns', value: kpiData.totalCampaigns, icon: Target, color: 'text-accent-primary', bg: 'bg-accent-primary-dim' },
  { label: 'Active Loops', value: kpiData.activeLoops, icon: RefreshCw, color: 'text-accent-success', bg: 'bg-green-900/30' },
  { label: 'Total Spend', value: `$${(kpiData.totalSpend / 1000).toFixed(1)}K`, icon: DollarSign, color: 'text-accent-warning', bg: 'bg-amber-900/30' },
  { label: 'Avg ROAS', value: `${kpiData.avgRoas}x`, icon: TrendingUp, color: 'text-accent-secondary', bg: 'bg-purple-900/30' },
];

const statusStyles: Record<string, string> = {
  running: 'bg-green-900/40 text-green-400 border-green-800',
  paused: 'bg-amber-900/40 text-amber-400 border-amber-800',
  completed: 'bg-blue-900/40 text-blue-400 border-blue-800',
};

const activityIcons: Record<string, { color: string; dot: string }> = {
  decide: { color: 'text-accent-secondary', dot: 'bg-purple-500' },
  create: { color: 'text-accent-success', dot: 'bg-green-500' },
  execute: { color: 'text-accent-primary', dot: 'bg-cyan-500' },
  analyze: { color: 'text-accent-warning', dot: 'bg-amber-500' },
  pause: { color: 'text-accent-danger', dot: 'bg-red-500' },
  update: { color: 'text-accent-info', dot: 'bg-blue-500' },
};

export default function Dashboard() {
  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpiCards.map((card, i) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1, duration: 0.4 }}
            className="bg-bg-surface border border-border-subtle rounded-card p-5 hover:border-border-active transition-colors"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-text-tertiary text-sm">{card.label}</p>
                <p className="text-2xl font-bold text-text-primary mt-1">{card.value}</p>
              </div>
              <div className={`p-2 rounded-lg ${card.bg}`}>
                <card.icon className={`w-5 h-5 ${card.color}`} />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Loops Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 bg-bg-surface border border-border-subtle rounded-card overflow-hidden"
        >
          <div className="px-5 py-4 border-b border-border-subtle flex items-center justify-between">
            <h2 className="text-lg font-semibold text-text-primary">Active Loops</h2>
            <span className="text-xs text-text-tertiary">{loops.length} loops</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-xs text-text-tertiary border-b border-border-subtle">
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Iteration</th>
                  <th className="px-5 py-3 font-medium">Platforms</th>
                  <th className="px-5 py-3 font-medium">Budget / Spend</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loops.map((loop) => (
                  <tr key={loop.id} className="border-b border-border-subtle/50 hover:bg-bg-elevated/50 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="text-sm font-medium text-text-primary">{loop.name}</div>
                      <div className="text-xs text-text-tertiary">{loop.threadId.slice(0, 20)}...</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${statusStyles[loop.status]}`}>
                        {loop.status === 'running' && <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />}
                        {loop.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="text-sm text-text-primary">{loop.iteration} / {loop.maxIterations}</div>
                      <div className="w-24 h-1.5 bg-bg-input rounded-full mt-1">
                        <div
                          className="h-full bg-accent-primary rounded-full transition-all"
                          style={{ width: `${(loop.iteration / loop.maxIterations) * 100}%` }}
                        />
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
                      <div className="text-sm text-text-primary">${loop.budget.toLocaleString()} / ${loop.spend.toLocaleString()}</div>
                      <div className="w-24 h-1.5 bg-bg-input rounded-full mt-1">
                        <div
                          className="h-full bg-accent-warning rounded-full"
                          style={{ width: `${Math.min((loop.spend / loop.budget) * 100, 100)}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex gap-1">
                        {loop.status === 'running' ? (
                          <button className="p-1.5 rounded-lg text-amber-400 hover:bg-amber-900/30 transition-colors" title="Pause">
                            <Pause className="w-4 h-4" />
                          </button>
                        ) : loop.status === 'paused' ? (
                          <button className="p-1.5 rounded-lg text-green-400 hover:bg-green-900/30 transition-colors" title="Resume">
                            <Play className="w-4 h-4" />
                          </button>
                        ) : null}
                        <button className="p-1.5 rounded-lg text-text-tertiary hover:text-accent-danger hover:bg-red-900/30 transition-colors" title="Stop">
                          <AlertTriangle className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Donut Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="bg-bg-surface border border-border-subtle rounded-card p-5"
          >
            <h3 className="text-sm font-semibold text-text-primary mb-4">Budget Distribution</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={donutData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {donutData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#111827',
                    border: '1px solid #1E293B',
                    borderRadius: '8px',
                    color: '#F8FAFC',
                    fontSize: '12px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-3 justify-center mt-2">
              {donutData.map((d) => (
                <div key={d.name} className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.fill }} />
                  <span className="text-xs text-text-secondary">{d.name}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Activity Feed */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="bg-bg-surface border border-border-subtle rounded-card p-5"
          >
            <h3 className="text-sm font-semibold text-text-primary mb-4">Recent Activity</h3>
            <div className="space-y-3">
              {activityFeed.map((item, i) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.7 + i * 0.05 }}
                  className="flex gap-3"
                >
                  <div className="flex flex-col items-center">
                    <div className={`w-2 h-2 rounded-full ${activityIcons[item.type]?.dot || 'bg-gray-500'}`} />
                    {i < activityFeed.length - 1 && <div className="w-px h-full bg-border-subtle mt-1" />}
                  </div>
                  <div className="pb-3">
                    <p className="text-sm text-text-primary">{item.action}</p>
                    <p className="text-xs text-text-tertiary">{item.details}</p>
                    <p className="text-[10px] text-text-tertiary mt-0.5">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
