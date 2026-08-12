import type { 
  UserData, 
  StatsData, 
  DecisionItem, 
  DecisionBriefData,
  QueryTemplateItem,
  RecentSearchItem,
  AnalyticsMetrics,
  VolumeTrendPoint,
  CategoryAccuracyPoint,
  OutcomePoint,
  PlaybookItem
} from '../types/dashboard';

export const mockUserData: UserData = {
  id: 'usr_1',
  name: 'Sarah Jenkins',
  email: 'sarah.jenkins@cortex-intel.com',
  role: 'Chief Operations Officer',
  avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256',
};

export const mockStatsData: StatsData = {
  queriesWeek: 12,
  avgTime: '2.3 hrs',
  pendingApprovals: 3,
  alerts: 1,
};

export const mockRecentQueries: string[] = [
  'Vendor MOQ negotiation',
  'Brand strategy alignment',
  'Q4 Marketing reallocation',
  'EU Logistics vendor review',
];

export const mockDecisions: DecisionItem[] = [
  {
    id: 'dec-101',
    title: 'Ingredient supplier change - Brand X',
    status: 'Approved',
    confidence: 87,
    owner: 'Sarah Jenkins',
    date: 'Oct 24, 2023',
    category: 'Supply Chain',
    description: 'Switching primary raw component provider to reduce unit lead time by 18 days while keeping strict QA guidelines.',
    impactScore: '+$140k Annual Savings',
  },
  {
    id: 'dec-102',
    title: 'Q4 Marketing Budget Reallocation',
    status: 'Pending',
    confidence: 65,
    owner: 'Michael Chen',
    date: 'Oct 23, 2023',
    category: 'Finance & Growth',
    description: 'Shifting 25% performance ad spend to high-converting enterprise account-based marketing campaigns.',
    impactScore: 'Estimated +14% Pipeline',
  },
  {
    id: 'dec-103',
    title: 'New Facility Location - EU',
    status: 'Rejected',
    confidence: 92,
    owner: 'Elena Rodriguez',
    date: 'Oct 21, 2023',
    category: 'Infrastructure',
    description: 'Proposed Frankfurt hub deferred due to regulatory compliance changes in regional energy tariffs.',
    impactScore: 'Avoided $2.1M CapEx',
  },
  {
    id: 'dec-104',
    title: 'SaaS Vendor Contract Consolidation',
    status: 'Approved',
    confidence: 94,
    owner: 'David Vance',
    date: 'Oct 19, 2023',
    category: 'Procurement',
    description: 'Merged 4 separate monitoring tools into unified telemetry stack with multi-year enterprise volume discount.',
    impactScore: '+$85k Cost Reduction',
  },
  {
    id: 'dec-105',
    title: 'Tier-1 SLA Penalty Clause Adjustment',
    status: 'Pending',
    confidence: 78,
    owner: 'Alex Rivera',
    date: 'Oct 18, 2023',
    category: 'Legal & Risk',
    description: 'Modifying standard payout threshold from 99.9% uptime to 99.95% tier for mission-critical core microservices.',
    impactScore: 'Risk Mitigation',
  },
];

export const mockDecisionBrief: DecisionBriefData = {
  id: 'brief-2024-001',
  title: 'Vendor Negotiation Decision - Brand Coffee Co.',
  querySubmittedAt: 'Query submitted 2 mins ago',
  generatedAt: 'Generated via 5 historical precedents',
  recommendation: 'Negotiate on MOQ but hold on price. Prioritize flexibility on payment terms.',
  strategicNote: 'This aligns with our Q3 sourcing strategy to preserve cash flow while maintaining supplier relationships. Previous attempts to negotiate price aggressively with similar scale vendors resulted in quality compromises.',
  confidence: 87,
  precedents: [
    {
      id: 'prec-1',
      title: 'Supplier Y negotiation (Feb 2024)',
      outcome: 'Approved - Saved 12% on ingredient cost',
      keyDetail: 'MOQ: 40K -> 15K',
      relevanceScore: 92,
      date: 'Feb 2024',
      fullDetails: 'Successfully negotiated order volume baseline down from 40k to 15k units per batch with quarterly review cadence without incurring unit cost surcharges.',
    },
    {
      id: 'prec-2',
      title: 'Vendor Z Renewal (Nov 2023)',
      outcome: 'Rejected - Terms inflexible',
      keyDetail: 'Price +5%',
      relevanceScore: 85,
      date: 'Nov 2023',
      fullDetails: 'Vendor insisted on strict 5% annual price escalation with non-negotiable minimum order requirements, leading to contract termination.',
    },
    {
      id: 'prec-3',
      title: 'Alpha Co Initial Contract (Aug 2023)',
      outcome: 'Approved - Net 60 days',
      keyDetail: 'Payment Terms',
      relevanceScore: 78,
      date: 'Aug 2023',
      fullDetails: 'Secured extended Net 60 payment terms to buffer seasonal inventory fluctuations during initial Q3 ramp.',
    },
  ],
  risks: [
    {
      id: 'risk-1',
      type: 'SUPPLY CHAIN RISK',
      description: 'Vendor is concentrated in region with weather volatility',
      severity: 'medium',
      mitigation: 'Establish secondary regional backup supplier and maintain 15-day safety buffer stock in centralized warehouse.',
    },
    {
      id: 'risk-2',
      type: 'FINANCIAL RISK',
      description: 'Requested payment terms (Net 30) below standard Net 45',
      severity: 'low',
      mitigation: 'Offer 2% early settlement discount if Net 30 term is strictly mandated by vendor billing software.',
    },
    {
      id: 'risk-3',
      type: 'COMPLIANCE RISK',
      description: 'Pending updated sustainability certification for 2024',
      severity: 'low',
      mitigation: 'Insert conditional clause requiring valid ISO 14001 audit completion prior to Q3 delivery milestone.',
    },
  ],
  alternatives: [
    {
      id: 'alt-1',
      action: "Accept vendor's MOQ, increase internal forecast",
      pros: [
        'Secures unit pricing at -5%',
        'Reduces frequency of ordering',
      ],
      cons: [
        'Ties up $45k in working capital',
        'High risk of spoilage based on current sales velocity',
      ],
    },
  ],
  approvalRequiredFrom: ['VP Supply Chain', 'Finance Lead'],
  status: 'Awaiting approval',
  transparency: {
    retrievedDocuments: [
      {
        id: 'doc-1',
        title: 'Supplier Y negotiation (Feb 2024)',
        source: 'Historical decision',
        relevanceScore: 92,
        explanation: 'Closest match on MOQ, payment terms, and supplier flexibility. The approved outcome improved cost without sacrificing quality.',
        note: '91% historical accuracy on similar procurement decisions',
      },
      {
        id: 'doc-2',
        title: 'Brand Coffee Co. sourcing policy',
        source: 'Playbook',
        relevanceScore: 88,
        explanation: 'Provides the active guardrails for payment terms, vendor onboarding, and approval thresholds.',
        note: 'Complies with active vendor policy',
      },
      {
        id: 'doc-3',
        title: 'Vendor Z renewal postmortem',
        source: 'Outcome review',
        relevanceScore: 81,
        explanation: 'Relevant because it documents the downside of pushing too hard on price and losing flexibility in the contract.',
      },
    ],
    confidenceReasoning: [
      {
        summary: 'High confidence because the closest historical match was approved and had strong outcome accuracy.',
        detail: 'Similar decision in Feb 2024 had 91% accuracy and produced measurable savings, which increases confidence in the current recommendation.',
      },
      {
        summary: 'Confidence is reduced slightly by missing region-specific risk data.',
        detail: 'We do not yet have recent supply chain telemetry for the target region, so the model avoids over-committing on execution details.',
      },
    ],
    playbookChecks: [
      {
        check: 'Complies with Brand A vendor policy',
        passed: true,
        detail: 'Payment-term guidance and MOQ handling stay within the approved Brand A procurement guardrails.',
      },
      {
        check: 'Vendor negotiation threshold reviewed',
        passed: true,
        detail: 'The recommendation stays under the escalation threshold for procurement approval.',
      },
      {
        check: 'Cross-check against active SLA policy',
        passed: true,
        detail: 'The recommendation preserves SLA protections and does not relax service penalties.',
      },
    ],
    missingData: [
      {
        label: 'Supply chain risk',
        detail: 'No recent supply chain risk data for the target region.',
      },
      {
        label: 'Vendor capacity',
        detail: 'Latest vendor capacity figures were not present in the retrieved evidence set.',
      },
    ],
  },
};

export const mockSearchTemplates: QueryTemplateItem[] = [
  {
    id: 'tmpl-1',
    label: 'Vendor MOQ & Terms',
    description: 'Evaluate supplier minimum order quantities and payment terms',
    defaultQuery: 'Negotiate vendor MOQ for Q3 coffee bean procurement',
    category: 'Procurement',
  },
  {
    id: 'tmpl-2',
    label: 'Brand Reallocation',
    description: 'Analyze Q4 ad budget reallocation across active product lines',
    defaultQuery: 'Reallocate 25% marketing budget to enterprise ABM campaigns',
    category: 'Strategy',
  },
  {
    id: 'tmpl-3',
    label: 'EU Supply Chain Audit',
    description: 'Audit EU facility compliance and regional energy tariff risks',
    defaultQuery: 'Evaluate regulatory compliance risks for new EU distribution hub',
    category: 'Supply Chain',
  },
  {
    id: 'tmpl-4',
    label: 'SaaS License Consolidation',
    description: 'Evaluate multi-year enterprise telemetry vendor contract renewal',
    defaultQuery: 'Consolidate 4 software telemetry vendors into single enterprise contract',
    category: 'Product',
  },
];

export const mockRecentSearchItems: RecentSearchItem[] = [
  {
    id: 'rec-1',
    query: 'Vendor MOQ negotiation - Brand Coffee Co.',
    timestamp: '2 mins ago',
    duration: '1.4s',
    status: 'Completed',
  },
  {
    id: 'rec-2',
    query: 'Brand strategy Q4 marketing budget',
    timestamp: '1 hour ago',
    duration: '1.8s',
    status: 'Approved',
  },
  {
    id: 'rec-3',
    query: 'EU facility location & regulatory risk',
    timestamp: 'Yesterday',
    duration: '2.1s',
    status: 'Completed',
  },
  {
    id: 'rec-4',
    query: 'SaaS monitoring stack consolidation',
    timestamp: '3 days ago',
    duration: '1.2s',
    status: 'Completed',
  },
];

export const mockAnalyticsMetrics: AnalyticsMetrics = {
  totalDecisions: 148,
  avgDecisionTime: 2.1,
  approvalRate: 94.2,
  riskAlerts: 3,
  trends: {
    queriesThisMonth: 148,
    queriesLastMonth: 129,
    timeThisMonth: 2.1,
    timeLastMonth: 2.5,
  },
};

export const mockVolumeTrend: VolumeTrendPoint[] = [
  { date: 'Oct 1', volume: 3, avgTime: 3.2 },
  { date: 'Oct 3', volume: 5, avgTime: 2.9 },
  { date: 'Oct 5', volume: 4, avgTime: 3.0 },
  { date: 'Oct 7', volume: 7, avgTime: 2.6 },
  { date: 'Oct 9', volume: 6, avgTime: 2.5 },
  { date: 'Oct 11', volume: 8, avgTime: 2.3 },
  { date: 'Oct 13', volume: 5, avgTime: 2.4 },
  { date: 'Oct 15', volume: 9, avgTime: 2.1 },
  { date: 'Oct 17', volume: 11, avgTime: 1.9 },
  { date: 'Oct 19', volume: 10, avgTime: 2.0 },
  { date: 'Oct 21', volume: 12, avgTime: 1.8 },
  { date: 'Oct 23', volume: 14, avgTime: 1.7 },
  { date: 'Oct 25', volume: 15, avgTime: 1.6 },
  { date: 'Oct 27', volume: 13, avgTime: 1.8 },
  { date: 'Oct 29', volume: 16, avgTime: 1.5 },
];

export const mockCategoryAccuracy: CategoryAccuracyPoint[] = [
  { category: 'Procurement', accuracy: 96.4 },
  { category: 'Supply Chain', accuracy: 92.1 },
  { category: 'Product', accuracy: 94.0 },
  { category: 'Strategy', accuracy: 88.5 },
];

export const mockOutcomeData: OutcomePoint[] = [
  { status: 'Approved', count: 98, color: '#10B981' },
  { status: 'Pending', count: 24, color: '#D97706' },
  { status: 'Revised', count: 18, color: '#3B82F6' },
  { status: 'Rejected', count: 8, color: '#EF4444' },
];

export const mockAnalyticsInsights: string[] = [
  'Supplier MOQ decisions have accelerated by 35% following Q3 playbook deployment.',
  'Supply Chain category shows a 4.2% accuracy improvement after integrating weather volatility telemetry.',
  'Average decision approval cycle reduced from 2.5 hrs to 2.1 hrs across enterprise tier accounts.',
];

// ----------------------------------------------------
// Playbooks Mock Dataset
// ----------------------------------------------------

export const mockPlaybooksData: PlaybookItem[] = [
  {
    id: 'pb-101',
    title: 'Vendor Management Playbook',
    description: 'Sourcing criteria, negotiation templates, vendor vetting checklist and payment terms.',
    category: 'Vendor Management',
    brands: ['All Brands', 'Brand Coffee Co.'],
    lastUpdated: '3 days ago',
    tags: ['Procurement', 'All Brands', 'SLA', 'Negotiation'],
    sections: [
      {
        id: 'sec-1',
        title: '1. Vendor Sourcing & Screening Guidelines',
        content: 'All raw component suppliers must pass ISO 9001 quality audits and submit 3 years of audited financial statements before initial contract approval.',
        subsections: [
          { title: 'Minimum Order Quantities (MOQ)', content: 'Base MOQ limit is capped at 15,000 units per batch for core lines.' },
          { title: 'Payment Terms Standard', content: 'Standard target term is Net 45. Net 30 is acceptable only with 2% cash settlement discount.' }
        ]
      },
      {
        id: 'sec-2',
        title: '2. Contract Escalation Thresholds',
        content: 'Contract values exceeding $100k require dual sign-off from VP of Supply Chain and Finance Lead.',
      }
    ]
  },
  {
    id: 'pb-102',
    title: 'Brand Strategy Alignment',
    description: 'Voice and tone, visual identity, market positioning guidelines, and Q4 budget reallocation rules.',
    category: 'Brand Strategy',
    brands: ['Brand A'],
    lastUpdated: '1 week ago',
    tags: ['Strategy', 'Brand A', 'Marketing', 'ABM'],
    sections: [
      {
        id: 'sec-1',
        title: '1. Brand Voice & Typography Rules',
        content: 'Brand A maintains an authoritative, empathetic, and premium tone across all digital assets.',
      },
      {
        id: 'sec-2',
        title: '2. Performance Ad Spend Thresholds',
        content: 'Reallocate up to 25% of underperforming ad channels to enterprise ABM campaigns when customer acquisition cost exceeds target by 15%.',
      }
    ]
  },
  {
    id: 'pb-103',
    title: 'Product Development Roadmap Guidelines',
    description: 'Feature prioritization matrix, telemetry compliance checklist, and QA testing gates.',
    category: 'Product Development',
    brands: ['Brand B'],
    lastUpdated: '2 days ago',
    tags: ['Product', 'Brand B', 'Telemetry', 'QA Gates'],
    sections: [
      {
        id: 'sec-1',
        title: '1. Feature Prioritization (RICE Framework)',
        content: 'Prioritize feature requests yielding high reach and impact scores with minimal engineering effort.',
      }
    ]
  },
  {
    id: 'pb-104',
    title: 'Operations & Fulfillment Playbook',
    description: 'Warehouse SLA benchmarks, regional carrier dispatch rules, and emergency inventory safety buffers.',
    category: 'Operations',
    brands: ['All Brands'],
    lastUpdated: '5 days ago',
    tags: ['Operations', 'All Brands', 'Supply Chain', 'Warehousing'],
    sections: [
      {
        id: 'sec-1',
        title: '1. Fulfillment Uptime & Dispatch Timelines',
        content: 'Same-day dispatch required for all orders logged before 14:00 EST.',
      }
    ]
  },
  {
    id: 'pb-105',
    title: 'Supplier Dispute & Penalty Protocol',
    description: 'Contractual dispute resolution workflows, SLA penalty clauses, and risk mitigation strategies.',
    category: 'Vendor Management',
    brands: ['Brand Coffee Co.'],
    lastUpdated: 'Yesterday',
    tags: ['Procurement', 'Brand Coffee Co.', 'SLA', 'Legal'],
    sections: [
      {
        id: 'sec-1',
        title: '1. SLA Penalty Calculation',
        content: 'Impose 1.5% daily unit credit for delayed shipments exceeding 3 business days.',
      }
    ]
  },
  {
    id: 'pb-106',
    title: 'Multi-Region Distribution Framework',
    description: 'EU expansion logistics rules, regional energy tariff compliance, and environmental audits.',
    category: 'Brand Strategy',
    brands: ['All Brands'],
    lastUpdated: '4 days ago',
    tags: ['Strategy', 'EU', 'Logistics', 'Compliance'],
    sections: [
      {
        id: 'sec-1',
        title: '1. EU Regulatory Compliance Checklist',
        content: 'Ensure ISO 14001 environmental certification is verified before establishing regional hubs.',
      }
    ]
  }
];
