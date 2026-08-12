/**
 * TypeScript Data Models for Cortex Decision Intelligence Dashboard
 */

export type NavigationItem = 'dashboard' | 'decisions' | 'playbooks' | 'vendors' | 'analytics' | 'settings';

export interface UserData {
  id: string;
  name: string;
  email: string;
  role: string;
  avatarUrl?: string;
}

export interface StatsData {
  queriesWeek: number;
  avgTime: string;
  pendingApprovals: number;
  alerts: number;
}

export type DecisionStatus = 'Approved' | 'Pending' | 'Rejected';

export interface DecisionItem {
  id: string;
  title: string;
  status: DecisionStatus;
  confidence: number;
  owner: string;
  date: string;
  category?: string;
  description?: string;
  impactScore?: string;
}

// ----------------------------------------------------
// Decision Brief Specifications
// ----------------------------------------------------

export interface PrecedentItem {
  id: string;
  title: string;
  outcome: string;
  keyDetail: string;
  relevanceScore: number;
  date?: string;
  fullDetails?: string;
}

export type RiskSeverity = 'high' | 'medium' | 'low';

export interface RiskItem {
  id: string;
  type: string;
  description: string;
  severity: RiskSeverity;
  mitigation?: string;
}

export interface AlternativeItem {
  id: string;
  action: string;
  pros: string[];
  cons: string[];
}

export interface RetrievedDocumentInsight {
  id: string;
  title: string;
  source: string;
  relevanceScore: number;
  explanation: string;
  note?: string;
}

export interface PlaybookCheckItem {
  check: string;
  passed: boolean;
  detail: string;
}

export interface MissingDataItem {
  label: string;
  detail: string;
}

export interface ConfidenceReasoningItem {
  summary: string;
  detail: string;
}

export interface BriefTransparencyData {
  retrievedDocuments: RetrievedDocumentInsight[];
  confidenceReasoning: ConfidenceReasoningItem[];
  playbookChecks: PlaybookCheckItem[];
  missingData: MissingDataItem[];
}

export interface DecisionBriefData {
  id: string;
  decisionId?: string;
  title: string;
  querySubmittedAt?: string;
  generatedAt: string;
  recommendation: string;
  strategicNote?: string;
  confidence: number;
  precedents: PrecedentItem[];
  risks: RiskItem[];
  alternatives: AlternativeItem[];
  approvalRequiredFrom: string[];
  status?: string;
  transparency?: BriefTransparencyData;
}

export interface DecisionBriefProps {
  brief?: DecisionBriefData;
  onApprove?: (metadata: {
    briefId: string;
    decisionId?: string;
    title: string;
    category: string;
    brands: string[];
    confidence: number;
    approvedAt: string;
  }) => void;
  onRequestInfo?: () => void;
  onBack?: () => void;
  onClose?: () => void;
}

// ----------------------------------------------------
// Search Interface Specifications
// ----------------------------------------------------

export interface RecentSearchItem {
  id: string;
  query: string;
  timestamp: string;
  status?: 'Completed' | 'Pending' | 'Approved';
  duration?: string;
}

export interface QueryTemplateItem {
  id: string;
  label: string;
  description: string;
  defaultQuery: string;
  category: 'Procurement' | 'Strategy' | 'Product' | 'Supply Chain';
}

export interface QueryDetectionInfo {
  category: 'Procurement' | 'Strategy' | 'Product' | 'Supply Chain' | 'General';
  brandsAffected: number;
  estimatedTime: string;
}

export interface SearchInterfaceProps {
  onSubmitQuery?: (data: { query: string; category: string; detection?: QueryDetectionInfo }) => void;
  recentQueries?: RecentSearchItem[];
  templates?: QueryTemplateItem[];
  placeholder?: string;
  initialQuery?: string;
}

// ----------------------------------------------------
// Analytics Specifications
// ----------------------------------------------------

export interface AnalyticsMetrics {
  totalDecisions: number;
  avgDecisionTime: number; // hours
  approvalRate: number; // 0-100%
  riskAlerts: number;
  trends: {
    queriesThisMonth: number;
    queriesLastMonth: number;
    timeThisMonth: number;
    timeLastMonth: number;
  };
}

export interface VolumeTrendPoint {
  date: string;
  volume: number;
  avgTime: number;
}

export interface CategoryAccuracyPoint {
  category: string;
  accuracy: number;
}

export interface OutcomePoint {
  status: 'Approved' | 'Pending' | 'Revised' | 'Rejected';
  count: number;
  color?: string;
}

export interface AnalyticsChartData {
  volumeTrend: VolumeTrendPoint[];
  accuracyByCategory: CategoryAccuracyPoint[];
  outcomes: OutcomePoint[];
}

export interface AnalyticsDashboardProps {
  metrics?: AnalyticsMetrics;
  chartData?: AnalyticsChartData;
  insights?: string[];
  dateRange?: { start: string; end: string };
  onRangeChange?: (range: '7d' | '30d' | '90d') => void;
}

// ----------------------------------------------------
// Playbooks Browser Specifications
// ----------------------------------------------------

export type PlaybookCategory = 'Vendor Management' | 'Brand Strategy' | 'Product Development' | 'Operations';

export interface PlaybookSubSection {
  title: string;
  content: string;
}

export interface PlaybookSection {
  id: string;
  title: string;
  content: string;
  subsections?: PlaybookSubSection[];
}

export interface PlaybookItem {
  id: string;
  title: string;
  description: string;
  category: PlaybookCategory;
  brands: string[];
  lastUpdated: string;
  tags: string[];
  sections: PlaybookSection[];
  autoGenerated?: boolean;
  evidenceCount?: number;
  contradictionCount?: number;
  reviewStatus?: 'draft' | 'needs_review' | 'approved';
  source?: string;
  generatedFromDecisionIds?: string[];
}

export interface PlaybookFilterState {
  brand: string;
  categories: PlaybookCategory[];
  lastUpdatedRange: 'Any time' | 'This week' | 'This month';
}

export interface PlaybookBrowserFilterOptions {
  brands: string[];
  categories: PlaybookCategory[];
}

export interface PlaybooksBrowserProps {
  playbooks?: PlaybookItem[];
  filters: PlaybookBrowserFilterOptions;
  onSelectPlaybook?: (playbook: PlaybookItem) => void;
  onNewPlaybook?: () => void;
}

export interface DashboardProps {
  user?: UserData;
  recentQueries?: string[];
  stats?: StatsData;
  decisions?: DecisionItem[];
  activeNav?: NavigationItem;
  onNavigate?: (path: NavigationItem) => void;
  onSelectDecision?: (decision: DecisionItem) => void;
}

export interface SidebarProps {
  activeNav?: NavigationItem;
  onNavigate?: (path: NavigationItem) => void;
  isDarkTheme?: boolean;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export interface TopNavProps {
  user?: UserData;
  onSearchSubmit?: (query: string) => void;
  onToggleMobileSidebar?: () => void;
  isDarkTheme?: boolean;
  onToggleTheme?: () => void;
}

export interface HeroSectionProps {
  subheading?: string;
  recentQueries?: string[];
  onSearchSubmit?: (query: string) => void;
}

export interface StatsCardsProps {
  stats?: StatsData;
}

export interface ActivityFeedProps {
  decisions?: DecisionItem[];
  onSelectDecision?: (decision: DecisionItem) => void;
}
