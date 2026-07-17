import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Eye, Brain, Lightbulb, Play, RotateCcw,
  ChevronDown, ChevronUp, Terminal, Sparkles
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { thinkProcess, llmDecision, donutData } from '@/data/mock';

const nodeIcons: Record<string, React.ElementType> = {
  OBSERVE: Eye,
  ANALYZE: Brain,
  DECIDE: Lightbulb,
  EXECUTE: Play,
  REFLECT: RotateCcw,
};

const nodeColors: Record<string, { border: string; text: string; bg: string; glow: string }> = {
  completed: {
    border: 'border-green-500/50',
    text: 'text-green-400',
    bg: 'bg-green-900/20',
    glow: 'shadow-green-500/10',
  },
  active: {
    border: 'border-accent-primary',
    text: 'text-accent-primary',
    bg: 'bg-accent-primary-dim',
    glow: 'shadow-accent-primary/30',
  },
  pending: {
    border: 'border-border-subtle',
    text: 'text-text-tertiary',
    bg: 'bg-bg-elevated',
    glow: '',
  },
};

export default function Think() {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showResponse, setShowResponse] = useState(false);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">AI Thinking Process</h2>
          <p className="text-sm text-text-tertiary mt-0.5">LangGraph Observe-Analyze-Act loop visualization</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="px-3 py-1.5 bg-accent-primary-dim text-accent-primary rounded-lg text-sm font-medium">
            Iteration 4 / 10
          </span>
          <span className="px-3 py-1.5 bg-bg-surface border border-border-subtle text-text-secondary rounded-lg text-sm flex items-center gap-2">
            <Terminal className="w-4 h-4" />
            Thread: campaign_summer_...
          </span>
        </div>
      </div>

      {/* Flow Diagram */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-bg-surface border border-border-subtle rounded-card p-6"
      >
        <div className="flex items-center justify-between gap-3">
          {thinkProcess.map((node, i) => {
            const Icon = nodeIcons[node.name] || Eye;
            const colors = nodeColors[node.status];
            const isActive = node.status === 'active';

            return (
              <div key={node.id} className="flex items-center gap-3 flex-1">
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.15 }}
                  className={`flex-1 border-2 rounded-xl p-4 text-center relative ${colors.border} ${colors.bg} ${isActive ? 'shadow-lg ' + colors.glow : ''}`}
                >
                  {isActive && (
                    <motion.div
                      className="absolute inset-0 rounded-xl border-2 border-accent-primary opacity-50"
                      animate={{ scale: [1, 1.05, 1], opacity: [0.5, 0, 0.5] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    />
                  )}
                  <Icon className={`w-6 h-6 mx-auto mb-2 ${colors.text}`} />
                  <div className={`text-sm font-bold ${colors.text}`}>{node.name}</div>
                  <div className="text-[10px] text-text-tertiary mt-1">{node.timestamp}</div>
                  {node.status === 'completed' && (
                    <div className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                      <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </motion.div>
                {i < thinkProcess.length - 1 && (
                  <div className="flex-shrink-0 relative">
                    <svg className="w-6 h-6 text-border-active" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                    {thinkProcess[i].status === 'completed' && thinkProcess[i + 1].status === 'active' && (
                      <motion.div
                        className="absolute top-1/2 left-0 -translate-y-1/2 w-2 h-2 bg-accent-primary rounded-full"
                        animate={{ x: [0, 24, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                      />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </motion.div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Execution Log */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-[#0D1117] border border-border-subtle rounded-card overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-border-subtle flex items-center gap-2">
              <Terminal className="w-4 h-4 text-text-tertiary" />
              <span className="text-sm font-medium text-text-secondary">Execution Log</span>
            </div>
            <div className="p-4 font-mono text-xs space-y-2 max-h-[300px] overflow-y-auto">
              {thinkProcess.map((node) => (
                <div key={node.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-text-tertiary">[{node.timestamp}]</span>
                    <span className={`font-bold ${
                      node.status === 'completed' ? 'text-green-400' :
                      node.status === 'active' ? 'text-accent-primary' : 'text-text-tertiary'
                    }`}>[{node.name}]</span>
                  </div>
                  <p className="text-text-secondary pl-2 border-l-2 border-border-subtle ml-4">
                    {node.reasoning.slice(0, 120)}...
                  </p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Platform Scores */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-bg-surface border border-border-subtle rounded-card p-5"
          >
            <h3 className="text-sm font-semibold text-text-primary mb-4">Platform Scores</h3>
            <div className="space-y-3">
              {llmDecision.selectedPlatforms.map((p, i) => (
                <motion.div
                  key={p.name}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + i * 0.1 }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-text-primary">{p.displayName}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-text-primary">{p.score}/100</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        p.confidence === 'high' ? 'bg-green-900/40 text-green-400' :
                        p.confidence === 'medium' ? 'bg-amber-900/40 text-amber-400' :
                        'bg-red-900/40 text-red-400'
                      }`}>
                        {p.confidence}
                      </span>
                    </div>
                  </div>
                  <div className="h-2 bg-bg-input rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${p.score}%` }}
                      transition={{ delay: 0.5 + i * 0.1, duration: 0.8, ease: 'easeOut' }}
                      className="h-full rounded-full"
                      style={{
                        background: `linear-gradient(90deg, #06B6D4 ${100 - p.score}%, #8B5CF6)`,
                      }}
                    />
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* LLM Reasoning */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-bg-surface border border-border-subtle rounded-card p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <Brain className="w-5 h-5 text-accent-secondary" />
              <h3 className="text-sm font-semibold text-text-primary">LLM Reasoning</h3>
              <Sparkles className="w-4 h-4 text-accent-primary animate-pulse" />
            </div>
            <div className="bg-bg-elevated rounded-lg p-4 text-sm text-text-secondary leading-relaxed">
              {llmDecision.reasoning}
            </div>

            {/* Prompt Accordion */}
            <div className="mt-4 border border-border-subtle rounded-lg overflow-hidden">
              <button
                onClick={() => setShowPrompt(!showPrompt)}
                className="w-full px-4 py-3 flex items-center justify-between text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
              >
                <span>LLM Prompt (System)</span>
                {showPrompt ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showPrompt && (
                <div className="px-4 py-3 bg-[#0D1117] font-mono text-xs text-text-tertiary border-t border-border-subtle">
                  You are an expert digital advertising strategist. Analyze campaign requirements and platform data, then recommend the best platforms with detailed reasoning. Consider: audience alignment, cost efficiency, platform strengths, budget fit, creative format support, historical performance. Respond ONLY with JSON...
                </div>
              )}
            </div>

            {/* Response Accordion */}
            <div className="mt-2 border border-border-subtle rounded-lg overflow-hidden">
              <button
                onClick={() => setShowResponse(!showResponse)}
                className="w-full px-4 py-3 flex items-center justify-between text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
              >
                <span>LLM Response (JSON)</span>
                {showResponse ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showResponse && (
                <div className="px-4 py-3 bg-[#0D1117] font-mono text-xs text-text-tertiary border-t border-border-subtle overflow-x-auto">
                  <pre>{JSON.stringify(llmDecision, null, 2)}</pre>
                </div>
              )}
            </div>
          </motion.div>

          {/* Decision Output */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-bg-surface border border-border-subtle rounded-card p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <Lightbulb className="w-5 h-5 text-accent-warning" />
              <h3 className="text-sm font-semibold text-text-primary">AI Decision</h3>
            </div>

            {/* Selected Platforms */}
            <div className="mb-4">
              <p className="text-xs text-text-tertiary mb-2">Selected Platforms</p>
              <div className="space-y-2">
                {llmDecision.selectedPlatforms.map((p) => (
                  <div key={p.name} className="flex items-center justify-between bg-bg-elevated rounded-lg p-3">
                    <span className="text-sm text-text-primary">{p.displayName}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-bg-input rounded-full overflow-hidden">
                        <div className="h-full bg-accent-primary rounded-full" style={{ width: `${p.score}%` }} />
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        p.confidence === 'high' ? 'bg-green-900/40 text-green-400' :
                        'bg-amber-900/40 text-amber-400'
                      }`}>{p.confidence}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Budget Pie */}
            <div className="flex items-center gap-4 mb-4">
              <div className="w-24 h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donutData.slice(0, 3)} cx="50%" cy="50%" innerRadius={20} outerRadius={40} dataKey="value">
                      {donutData.slice(0, 3).map((d, i) => (
                        <Cell key={i} fill={d.fill} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #1E293B', borderRadius: '6px', color: '#F8FAFC', fontSize: '11px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div>
                <p className="text-xs text-text-tertiary">Budget Allocation</p>
                {Object.entries(llmDecision.budgetAllocation).map(([k, v]) => (
                  <div key={k} className="text-sm text-text-secondary">
                    {k.replace('_', ' ')}: <span className="text-text-primary font-medium">${v}/day</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Risk Factors */}
            <div>
              <p className="text-xs text-text-tertiary mb-2">Risk Factors</p>
              <div className="space-y-1">
                {llmDecision.riskFactors.map((risk, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-amber-400">
                    <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                    {risk}
                  </div>
                ))}
              </div>
            </div>

            {/* Strategy */}
            <div className="mt-4 p-3 bg-accent-primary-dim rounded-lg">
              <p className="text-xs text-text-tertiary mb-1">Overall Strategy</p>
              <p className="text-sm text-accent-primary">{llmDecision.overallStrategy}</p>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function AlertTriangle({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  );
}
