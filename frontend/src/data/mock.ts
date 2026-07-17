export interface Platform {
  id: string;
  name: string;
  displayName: string;
  type: 'mcp' | 'api';
  status: 'connected' | 'disconnected';
  objectives: string[];
  capabilities: string[];
  avgCpm: number;
  avgCpc: number;
  minBudget: number;
}

export interface Loop {
  id: string;
  name: string;
  status: 'running' | 'paused' | 'completed';
  iteration: number;
  maxIterations: number;
  platforms: string[];
  budget: number;
  spend: number;
  roas: number;
  threadId: string;
  nextAction: string;
}

export interface Campaign {
  id: string;
  name: string;
  objective: string;
  budget: number;
  dailyBudget: number;
  platforms: string[];
  status: 'active' | 'paused' | 'completed' | 'planned';
  startDate: string;
  spend: number;
  conversions: number;
  roas: number;
}

export interface ActivityItem {
  id: string;
  action: string;
  platform: string;
  details: string;
  timestamp: string;
  type: 'create' | 'update' | 'pause' | 'analyze' | 'decide' | 'execute';
}

export interface ThinkNode {
  id: string;
  name: string;
  status: 'completed' | 'active' | 'pending';
  reasoning: string;
  timestamp: string;
  icon: string;
}

export const platforms: Platform[] = [
  {
    id: 'google_ads',
    name: 'google_ads',
    displayName: 'Google Ads',
    type: 'mcp',
    status: 'connected',
    objectives: ['conversions', 'sales', 'traffic', 'leads', 'awareness'],
    capabilities: ['Search', 'Display', 'Shopping', 'Video', 'App'],
    avgCpm: 8.5,
    avgCpc: 2.5,
    minBudget: 1,
  },
  {
    id: 'meta_ads',
    name: 'meta_ads',
    displayName: 'Meta Ads',
    type: 'mcp',
    status: 'connected',
    objectives: ['awareness', 'sales', 'conversions', 'engagement', 'app_installs'],
    capabilities: ['Facebook', 'Instagram', 'Messenger', 'Audience Network'],
    avgCpm: 12.0,
    avgCpc: 1.5,
    minBudget: 1,
  },
  {
    id: 'amazon_dsp',
    name: 'amazon_dsp',
    displayName: 'Amazon DSP',
    type: 'mcp',
    status: 'disconnected',
    objectives: ['sales', 'conversions', 'awareness', 'retargeting'],
    capabilities: ['Display', 'Video', 'Audio', 'CTV'],
    avgCpm: 6.0,
    avgCpc: 1.2,
    minBudget: 50000,
  },
  {
    id: 'adform',
    name: 'adform',
    displayName: 'Adform FLOW',
    type: 'mcp',
    status: 'disconnected',
    objectives: ['conversions', 'awareness', 'traffic', 'video_views'],
    capabilities: ['Display', 'Video', 'Native', 'Audio', 'CTV'],
    avgCpm: 7.5,
    avgCpc: 1.8,
    minBudget: 1000,
  },
  {
    id: 'oceanengine',
    name: 'oceanengine',
    displayName: '巨量引擎',
    type: 'mcp',
    status: 'connected',
    objectives: ['awareness', 'sales', 'app_installs', 'livestream', 'conversions'],
    capabilities: ['抖音', '今日头条', '西瓜视频', '穿山甲'],
    avgCpm: 15.0,
    avgCpc: 3.0,
    minBudget: 300,
  },
  {
    id: 'tencent_ads',
    name: 'tencent_ads',
    displayName: '腾讯广告',
    type: 'api',
    status: 'connected',
    objectives: ['conversions', 'app_installs', 'awareness', 'sales'],
    capabilities: ['微信', 'QQ', '腾讯视频', '腾讯新闻'],
    avgCpm: 18.0,
    avgCpc: 2.8,
    minBudget: 50,
  },
  {
    id: 'kuaishou',
    name: 'kuaishou',
    displayName: '快手磁力引擎',
    type: 'api',
    status: 'connected',
    objectives: ['awareness', 'sales', 'app_installs', 'livestream'],
    capabilities: ['快手', '快手极速版', '磁力聚星'],
    avgCpm: 10.0,
    avgCpc: 2.0,
    minBudget: 100,
  },
  {
    id: 'baidu_ads',
    name: 'baidu_ads',
    displayName: '百度营销',
    type: 'api',
    status: 'disconnected',
    objectives: ['conversions', 'traffic', 'leads', 'sales'],
    capabilities: ['搜索推广', '信息流', '品牌专区', '聚屏'],
    avgCpm: 5.0,
    avgCpc: 4.0,
    minBudget: 50,
  },
];

export const loops: Loop[] = [
  {
    id: 'loop_001',
    name: 'Summer Sale 2024',
    status: 'running',
    iteration: 4,
    maxIterations: 10,
    platforms: ['google_ads', 'meta_ads', 'oceanengine'],
    budget: 5000,
    spend: 2340,
    roas: 3.2,
    threadId: 'campaign_summer_20240715',
    nextAction: 'REFLECT',
  },
  {
    id: 'loop_002',
    name: 'Brand Awareness Q3',
    status: 'paused',
    iteration: 2,
    maxIterations: 10,
    platforms: ['meta_ads', 'tencent_ads'],
    budget: 3000,
    spend: 890,
    roas: 1.8,
    threadId: 'campaign_brand_20240710',
    nextAction: 'ANALYZE',
  },
  {
    id: 'loop_003',
    name: 'App Install Campaign',
    status: 'completed',
    iteration: 10,
    maxIterations: 10,
    platforms: ['google_ads', 'kuaishou', 'oceanengine'],
    budget: 8000,
    spend: 7560,
    roas: 4.1,
    threadId: 'campaign_app_20240701',
    nextAction: 'END',
  },
];

export const campaigns: Campaign[] = [
  {
    id: 'camp_001',
    name: 'Summer Sale 2024',
    objective: 'sales',
    budget: 15000,
    dailyBudget: 500,
    platforms: ['google_ads', 'meta_ads', 'oceanengine'],
    status: 'active',
    startDate: '2024-07-01',
    spend: 7200,
    conversions: 145,
    roas: 3.2,
  },
  {
    id: 'camp_002',
    name: 'Brand Awareness Q3',
    objective: 'awareness',
    budget: 10000,
    dailyBudget: 300,
    platforms: ['meta_ads', 'tencent_ads'],
    status: 'active',
    startDate: '2024-07-10',
    spend: 2100,
    conversions: 34,
    roas: 1.8,
  },
  {
    id: 'camp_003',
    name: 'App Install Drive',
    objective: 'app_installs',
    budget: 20000,
    dailyBudget: 800,
    platforms: ['google_ads', 'kuaishou', 'oceanengine'],
    status: 'active',
    startDate: '2024-07-05',
    spend: 15600,
    conversions: 520,
    roas: 4.1,
  },
  {
    id: 'camp_004',
    name: 'Lead Generation',
    objective: 'conversions',
    budget: 8000,
    dailyBudget: 250,
    platforms: ['google_ads', 'baidu_ads'],
    status: 'paused',
    startDate: '2024-07-12',
    spend: 1200,
    conversions: 28,
    roas: 2.1,
  },
  {
    id: 'camp_005',
    name: 'Holiday Preview',
    objective: 'sales',
    budget: 25000,
    dailyBudget: 1000,
    platforms: ['google_ads', 'meta_ads', 'amazon_dsp', 'adform'],
    status: 'planned',
    startDate: '2024-08-01',
    spend: 0,
    conversions: 0,
    roas: 0,
  },
];

export const activityFeed: ActivityItem[] = [
  { id: 'act1', action: 'Platform Selected', platform: 'google_ads', details: 'AI selected Google Ads with score 92/100', timestamp: '2024-07-15T10:30:00Z', type: 'decide' },
  { id: 'act2', action: 'Loop Started', platform: 'all', details: 'Summer Sale 2024 loop started (max 10 iterations)', timestamp: '2024-07-15T10:25:00Z', type: 'create' },
  { id: 'act3', action: 'Campaign Created', platform: 'meta_ads', details: 'Created campaign on Meta Ads with $500 daily budget', timestamp: '2024-07-15T10:28:00Z', type: 'execute' },
  { id: 'act4', action: 'Budget Allocated', platform: 'oceanengine', details: 'Allocated $1800/day based on ROAS prediction', timestamp: '2024-07-15T10:27:00Z', type: 'analyze' },
  { id: 'act5', action: 'Loop Paused', platform: 'all', details: 'Brand Awareness Q3 paused - ROAS below threshold', timestamp: '2024-07-14T18:00:00Z', type: 'pause' },
  { id: 'act6', action: 'Optimization', platform: 'google_ads', details: 'Iteration 3 complete - increased budget by 15%', timestamp: '2024-07-15T09:00:00Z', type: 'update' },
];

export const thinkProcess = [
  {
    id: 'observe',
    name: 'OBSERVE',
    status: 'completed' as const,
    reasoning: 'Collected data from 8 connected platforms. Retrieved historical ROAS for similar ecommerce campaigns. Market: global, Budget: $15K, Objective: sales.',
    timestamp: '10:25:12',
    icon: 'Eye',
  },
  {
    id: 'analyze',
    name: 'ANALYZE',
    status: 'completed' as const,
    reasoning: 'LLM analysis: Google Ads scored 92/100 for sales objective (strong Shopping + Search). Meta Ads 88/100 (A+SC for ecommerce). OceanEngine 85/100 (Douyin live commerce). Amazon DSP excluded due to $50K minimum. Risk: high competition on Google CPC.',
    timestamp: '10:26:45',
    icon: 'Brain',
  },
  {
    id: 'decide',
    name: 'DECIDE',
    status: 'completed' as const,
    reasoning: 'Selected 3 platforms: Google Ads ($2000/day), Meta Ads ($1800/day), OceanEngine ($1200/day). Strategy: ROAS maximize with 15% exploration budget. Total daily: $5000. Risk factors: CPC inflation on Google, Meta iOS tracking limitations.',
    timestamp: '10:27:30',
    icon: 'Lightbulb',
  },
  {
    id: 'execute',
    name: 'EXECUTE',
    status: 'completed' as const,
    reasoning: 'Created 3 campaigns (all PAUSED). Google Ads: Shopping campaign with $2000/day. Meta Ads: A+SC with $1800/day. OceanEngine: Live commerce with $1200/day. Awaiting activation approval.',
    timestamp: '10:28:15',
    icon: 'Play',
  },
  {
    id: 'reflect',
    name: 'REFLECT',
    status: 'active' as const,
    reasoning: 'Monitoring performance data... Current ROAS 3.2x (above target 2.5x). Google performing best at 4.1x ROAS. Meta at 2.8x. OceanEngine at 2.5x. Recommend increasing Google budget by 20% in next iteration.',
    timestamp: '10:30:00',
    icon: 'RotateCcw',
  },
];

export const llmDecision = {
  reasoning: 'Based on the campaign objective (sales), target market (global), and budget ($15K), I analyzed all 8 platforms. Google Ads is the strongest performer for ecommerce sales with Shopping campaigns and high intent search traffic. Meta Ads offers excellent visual commerce through A+SC. OceanEngine provides access to Douyin\'s massive live commerce audience. I excluded Amazon DSP due to its $50K minimum budget requirement and Baidu due to weaker performance for direct sales objectives. The budget allocation prioritizes Google (40%) as the primary conversion driver, with Meta (36%) and OceanEngine (24%) providing complementary reach.',
  selectedPlatforms: [
    { name: 'google_ads', displayName: 'Google Ads', score: 92, confidence: 'high' },
    { name: 'meta_ads', displayName: 'Meta Ads', score: 88, confidence: 'high' },
    { name: 'oceanengine', displayName: '巨量引擎', score: 85, confidence: 'medium' },
  ],
  budgetAllocation: {
    google_ads: 2000,
    meta_ads: 1800,
    oceanengine: 1200,
  },
  riskFactors: [
    'Google CPC inflation may reduce ROAS over time',
    'Meta iOS tracking limitations could underreport conversions',
    'OceanEngine CPM volatility during peak hours',
  ],
  overallStrategy: 'ROAS-maximize strategy with 3-platform diversification. Primary focus on Google Shopping for high-intent conversions, Meta A+SC for visual discovery, and OceanEngine for live commerce engagement.',
};

export const kpiData = {
  totalCampaigns: 5,
  activeLoops: 2,
  totalSpend: 12400,
  avgRoas: 3.2,
};

export const donutData = [
  { name: 'Google Ads', value: 2000, fill: '#06B6D4' },
  { name: 'Meta Ads', value: 1800, fill: '#8B5CF6' },
  { name: 'OceanEngine', value: 1200, fill: '#10B981' },
  { name: 'Tencent Ads', value: 900, fill: '#F59E0B' },
  { name: 'Kuaishou', value: 600, fill: '#EF4444' },
];
