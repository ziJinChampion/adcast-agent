import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Search, Filter, Edit2, Play, Pause, Trash2,
  ChevronDown, ChevronUp, X, Target, DollarSign, TrendingUp
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { campaigns as initialCampaigns, platforms } from '@/data/mock';

const objectiveColors: Record<string, string> = {
  conversions: 'bg-blue-900/40 text-blue-400 border-blue-800',
  sales: 'bg-green-900/40 text-green-400 border-green-800',
  awareness: 'bg-purple-900/40 text-purple-400 border-purple-800',
  traffic: 'bg-cyan-900/40 text-cyan-400 border-cyan-800',
  leads: 'bg-amber-900/40 text-amber-400 border-amber-800',
  app_installs: 'bg-pink-900/40 text-pink-400 border-pink-800',
};

const statusColors: Record<string, string> = {
  active: 'bg-green-900/40 text-green-400 border-green-800',
  paused: 'bg-amber-900/40 text-amber-400 border-amber-800',
  completed: 'bg-blue-900/40 text-blue-400 border-blue-800',
  planned: 'bg-gray-900/40 text-gray-400 border-gray-800',
};

const pieColors = ['#06B6D4', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444'];

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState(initialCampaigns);
  const [statusFilter, setStatusFilter] = useState('All');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: '', objective: 'conversions', budget: '', dailyBudget: '',
    targetMarket: 'global', strategy: 'roas_maximize', selectedPlatforms: [] as string[],
  });

  const filtered = campaigns.filter((c) =>
    statusFilter === 'All' ? true : c.status === statusFilter.toLowerCase()
  );

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const newCamp = {
      id: `camp_${Date.now()}`,
      name: form.name,
      objective: form.objective,
      budget: Number(form.budget) || 0,
      dailyBudget: Number(form.dailyBudget) || 0,
      platforms: form.selectedPlatforms,
      status: 'planned' as const,
      startDate: new Date().toISOString().split('T')[0],
      spend: 0,
      conversions: 0,
      roas: 0,
    };
    setCampaigns([newCamp, ...campaigns]);
    setShowCreate(false);
    setForm({ name: '', objective: 'conversions', budget: '', dailyBudget: '', targetMarket: 'global', strategy: 'roas_maximize', selectedPlatforms: [] });
  };

  const togglePlatform = (id: string) => {
    setForm((prev) => ({
      ...prev,
      selectedPlatforms: prev.selectedPlatforms.includes(id)
        ? prev.selectedPlatforms.filter((p) => p !== id)
        : [...prev.selectedPlatforms, id],
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">Campaigns</h2>
          <p className="text-sm text-text-tertiary">Manage your ad campaigns across platforms</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-accent-primary text-white text-sm font-medium rounded-lg hover:bg-cyan-500 transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Campaign
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {['All', 'Active', 'Paused', 'Completed', 'Planned'].map((f) => (
          <button
            key={f}
            onClick={() => setStatusFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              statusFilter === f
                ? 'bg-accent-primary text-white'
                : 'bg-bg-surface text-text-secondary border border-border-subtle hover:bg-bg-elevated'
            }`}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-sm text-text-tertiary self-center">{filtered.length} campaigns</span>
      </div>

      {/* Campaigns Table */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-bg-surface border border-border-subtle rounded-card overflow-hidden"
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-text-tertiary border-b border-border-subtle">
                <th className="px-5 py-3 font-medium w-8"></th>
                <th className="px-5 py-3 font-medium">Campaign</th>
                <th className="px-5 py-3 font-medium">Objective</th>
                <th className="px-5 py-3 font-medium">Budget</th>
                <th className="px-5 py-3 font-medium">Platforms</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Spend</th>
                <th className="px-5 py-3 font-medium">Conv.</th>
                <th className="px-5 py-3 font-medium">ROAS</th>
                <th className="px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((camp) => {
                const isExpanded = expandedId === camp.id;
                const spendPct = camp.budget > 0 ? (camp.spend / camp.budget) * 100 : 0;

                return (
                  <>
                    <tr
                      key={camp.id}
                      onClick={() => setExpandedId(isExpanded ? null : camp.id)}
                      className="border-b border-border-subtle/50 hover:bg-bg-elevated/50 transition-colors cursor-pointer"
                    >
                      <td className="px-5 py-3.5">
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-text-tertiary" /> : <ChevronDown className="w-4 h-4 text-text-tertiary" />}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="text-sm font-medium text-text-primary">{camp.name}</div>
                        <div className="text-xs text-text-tertiary">{camp.startDate}</div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${objectiveColors[camp.objective] || 'bg-bg-elevated text-text-secondary'}`}>
                          {camp.objective}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="text-sm text-text-primary">${(camp.budget / 1000).toFixed(1)}K</div>
                        <div className="text-xs text-text-tertiary">${camp.dailyBudget}/day</div>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex gap-1 flex-wrap">
                          {camp.platforms.map((p) => (
                            <span key={p} className="px-1.5 py-0.5 bg-bg-elevated rounded text-[10px] text-text-secondary border border-border-subtle">
                              {p.replace('_', ' ')}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${statusColors[camp.status]}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${camp.status === 'active' ? 'bg-green-400 animate-pulse' : camp.status === 'paused' ? 'bg-amber-400' : 'bg-blue-400'}`} />
                          {camp.status}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="w-16">
                          <div className="h-1.5 bg-bg-input rounded-full overflow-hidden">
                            <div className="h-full bg-accent-warning rounded-full" style={{ width: `${Math.min(spendPct, 100)}%` }} />
                          </div>
                          <span className="text-xs text-text-tertiary">{spendPct.toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-text-primary">{camp.conversions}</td>
                      <td className="px-5 py-3.5">
                        <span className={`text-sm font-medium ${
                          camp.roas > 3 ? 'text-green-400' : camp.roas > 1 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {camp.roas > 0 ? `${camp.roas}x` : '-'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex gap-1">
                          <button className="p-1.5 rounded-lg text-text-tertiary hover:text-accent-primary hover:bg-bg-elevated transition-colors">
                            <Edit2 className="w-4 h-4" />
                          </button>
                          {camp.status === 'active' ? (
                            <button className="p-1.5 rounded-lg text-amber-400 hover:bg-amber-900/30 transition-colors">
                              <Pause className="w-4 h-4" />
                            </button>
                          ) : (
                            <button className="p-1.5 rounded-lg text-green-400 hover:bg-green-900/30 transition-colors">
                              <Play className="w-4 h-4" />
                            </button>
                          )}
                          <button className="p-1.5 rounded-lg text-text-tertiary hover:text-accent-danger hover:bg-red-900/30 transition-colors">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.tr
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <td colSpan={11} className="px-5 py-4 bg-bg-elevated/30">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                              {/* Platform Performance */}
                              <div>
                                <p className="text-xs text-text-tertiary mb-3">Platform Performance</p>
                                <div className="space-y-2">
                                  {camp.platforms.map((p, i) => (
                                    <div key={p} className="flex items-center justify-between bg-bg-surface rounded-lg p-3">
                                      <span className="text-sm text-text-primary">{p.replace('_', ' ')}</span>
                                      <div className="flex gap-4 text-xs text-text-tertiary">
                                        <span>Spend: <span className="text-text-primary">${(camp.spend / camp.platforms.length).toFixed(0)}</span></span>
                                        <span>ROAS: <span className={camp.roas > 2 ? 'text-green-400' : 'text-amber-400'}>{(camp.roas * (0.8 + i * 0.15)).toFixed(1)}x</span></span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>

                              {/* Budget Donut */}
                              <div>
                                <p className="text-xs text-text-tertiary mb-3">Budget Allocation</p>
                                <div className="flex items-center gap-4">
                                  <div className="w-28 h-28">
                                    <ResponsiveContainer width="100%" height="100%">
                                      <PieChart>
                                        <Pie data={camp.platforms.map((p, i) => ({ name: p, value: camp.budget / camp.platforms.length, fill: pieColors[i % pieColors.length] }))} cx="50%" cy="50%" innerRadius={25} outerRadius={45} dataKey="value">
                                          {camp.platforms.map((_, i) => (
                                            <Cell key={i} fill={pieColors[i % pieColors.length]} />
                                          ))}
                                        </Pie>
                                        <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1E293B', borderRadius: '6px', color: '#F8FAFC', fontSize: '11px' }} />
                                      </PieChart>
                                    </ResponsiveContainer>
                                  </div>
                                  <div className="space-y-1">
                                    {camp.platforms.map((p, i) => (
                                      <div key={p} className="flex items-center gap-2 text-xs">
                                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: pieColors[i % pieColors.length] }} />
                                        <span className="text-text-secondary">{p.replace('_', ' ')}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
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

      {/* Create Campaign Modal */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowCreate(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-bg-surface border border-border-subtle rounded-card p-6 w-full max-w-lg max-h-[85vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold text-text-primary">Create New Campaign</h3>
                <button onClick={() => setShowCreate(false)} className="p-1.5 rounded-lg text-text-tertiary hover:bg-bg-elevated transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-sm text-text-secondary mb-1.5">Campaign Name</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-4 py-2.5 bg-bg-input border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
                    placeholder="Summer Sale 2024"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-text-secondary mb-1.5">Objective</label>
                    <select
                      value={form.objective}
                      onChange={(e) => setForm({ ...form, objective: e.target.value })}
                      className="w-full px-4 py-2.5 bg-bg-input border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
                    >
                      <option value="conversions">Conversions</option>
                      <option value="sales">Sales</option>
                      <option value="awareness">Awareness</option>
                      <option value="traffic">Traffic</option>
                      <option value="leads">Leads</option>
                      <option value="app_installs">App Installs</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-text-secondary mb-1.5">Target Market</label>
                    <select
                      value={form.targetMarket}
                      onChange={(e) => setForm({ ...form, targetMarket: e.target.value })}
                      className="w-full px-4 py-2.5 bg-bg-input border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
                    >
                      <option value="global">Global</option>
                      <option value="domestic">Domestic</option>
                      <option value="overseas">Overseas</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-text-secondary mb-1.5">Total Budget ($)</label>
                    <input
                      type="number"
                      value={form.budget}
                      onChange={(e) => setForm({ ...form, budget: e.target.value })}
                      className="w-full px-4 py-2.5 bg-bg-input border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
                      placeholder="10000"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-text-secondary mb-1.5">Daily Budget ($)</label>
                    <input
                      type="number"
                      value={form.dailyBudget}
                      onChange={(e) => setForm({ ...form, dailyBudget: e.target.value })}
                      className="w-full px-4 py-2.5 bg-bg-input border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
                      placeholder="500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-text-secondary mb-1.5">Strategy</label>
                  <select
                    value={form.strategy}
                    onChange={(e) => setForm({ ...form, strategy: e.target.value })}
                    className="w-full px-4 py-2.5 bg-bg-input border border-border-subtle rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
                  >
                    <option value="roas_maximize">ROAS Maximize</option>
                    <option value="reach_maximize">Reach Maximize</option>
                    <option value="balanced">Balanced</option>
                    <option value="cost_minimize">Cost Minimize</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-text-secondary mb-2">Select Platforms</label>
                  <div className="grid grid-cols-2 gap-2">
                    {platforms.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => togglePlatform(p.id)}
                        className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left text-sm transition-colors ${
                          form.selectedPlatforms.includes(p.id)
                            ? 'border-accent-primary bg-accent-primary-dim text-accent-primary'
                            : 'border-border-subtle bg-bg-input text-text-secondary hover:border-border-active'
                        }`}
                      >
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${form.selectedPlatforms.includes(p.id) ? 'bg-accent-primary' : 'bg-border-subtle'}`} />
                        <span className="truncate">{p.displayName}</span>
                        <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] ${p.type === 'mcp' ? 'bg-purple-900/40 text-purple-400' : 'bg-bg-elevated text-text-tertiary'}`}>
                          {p.type.toUpperCase()}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    className="flex-1 py-2.5 border border-border-subtle text-text-secondary rounded-lg hover:bg-bg-elevated transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2.5 bg-accent-primary text-white rounded-lg hover:bg-cyan-500 transition-colors font-medium"
                  >
                    Create Campaign
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
