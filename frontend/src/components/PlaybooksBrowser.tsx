import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  Filter,
  PanelsTopLeft,
  Printer,
  RotateCcw,
  Share2,
  X,
} from 'lucide-react';
import type {
  PlaybookCategory,
  PlaybookItem,
  PlaybooksBrowserProps,
  PlaybookSection,
} from '../types/dashboard';

type LastUpdatedFilter = 'all' | 'week' | 'month';

const CATEGORY_TINTS: Record<
  PlaybookCategory,
  { header: string; accent: string; badge: string }
> = {
  'Vendor Management': {
    header: 'bg-[#FFFBEB]',
    accent: 'bg-amber-50 text-amber-700 border-amber-200',
    badge: 'bg-amber-100 text-amber-900 border-amber-200',
  },
  'Brand Strategy': {
    header: 'bg-[#F0FDF4]',
    accent: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    badge: 'bg-emerald-100 text-emerald-900 border-emerald-200',
  },
  'Product Development': {
    header: 'bg-[#F5F3FF]',
    accent: 'bg-violet-50 text-violet-700 border-violet-200',
    badge: 'bg-violet-100 text-violet-900 border-violet-200',
  },
  Operations: {
    header: 'bg-[#F0FDFA]',
    accent: 'bg-cyan-50 text-cyan-700 border-cyan-200',
    badge: 'bg-cyan-100 text-cyan-900 border-cyan-200',
  },
};

const DEFAULT_CATEGORIES: PlaybookCategory[] = [
  'Vendor Management',
  'Brand Strategy',
  'Product Development',
  'Operations',
];

const LAST_UPDATED_OPTIONS: Array<{ value: LastUpdatedFilter; label: string }> = [
  { value: 'week', label: 'This week' },
  { value: 'month', label: 'This month' },
  { value: 'all', label: 'All' },
];

function uniqueItems(items: string[]) {
  return Array.from(new Set(items.filter(Boolean)));
}

function normalizeRelativeAge(value: string) {
  const lower = value.toLowerCase();

  if (lower.includes('yesterday')) return 1;
  if (lower.includes('this week')) return 3;
  if (lower.includes('this month')) return 14;

  const dayMatch = lower.match(/(\d+)\s+day/);
  if (dayMatch) return Number(dayMatch[1]);

  const weekMatch = lower.match(/(\d+)\s+week/);
  if (weekMatch) return Number(weekMatch[1]) * 7;

  const monthMatch = lower.match(/(\d+)\s+month/);
  if (monthMatch) return Number(monthMatch[1]) * 30;

  return Number.POSITIVE_INFINITY;
}

function matchesLastUpdated(value: string, filter: LastUpdatedFilter) {
  if (filter === 'all') return true;
  const ageInDays = normalizeRelativeAge(value);

  if (filter === 'week') return ageInDays <= 7;
  if (filter === 'month') return ageInDays <= 30;
  return true;
}

function isPlaybookExpandable(section: PlaybookSection) {
  return Boolean(section.content || section.subsections?.length);
}

function buildPlaybookDocument(playbook: PlaybookItem) {
  const body = [
    playbook.title,
    '',
    playbook.description,
    '',
    `Category: ${playbook.category}`,
    `Brands: ${playbook.brands.join(', ')}`,
    `Last updated: ${playbook.lastUpdated}`,
    '',
    'Sections',
    ...playbook.sections.flatMap((section) => {
      const subsectionLines = section.subsections?.length
        ? section.subsections.flatMap((subsection) => [
            `  - ${subsection.title}`,
            `    ${subsection.content}`,
          ])
        : [];

      return [
        '',
        section.title,
        section.content,
        ...subsectionLines,
      ];
    }),
  ];

  return body.join('\n');
}

function PlaybookModal({
  playbook,
  onClose,
}: {
  playbook: PlaybookItem;
  onClose: () => void;
}) {
  const [openSectionIds, setOpenSectionIds] = useState<string[]>(
    playbook.sections[0] ? [playbook.sections[0].id] : [],
  );

  useEffect(() => {
    setOpenSectionIds(playbook.sections[0] ? [playbook.sections[0].id] : []);
  }, [playbook]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const toggleSection = (sectionId: string) => {
    setOpenSectionIds((current) =>
      current.includes(sectionId)
        ? current.filter((id) => id !== sectionId)
        : [...current, sectionId],
    );
  };

  const handleDownload = () => {
    const html = `<!doctype html>
<html>
  <head>
    <title>${playbook.title}</title>
    <meta charset="utf-8" />
    <style>
      body { font-family: Arial, sans-serif; padding: 32px; color: #111827; }
      h1 { margin: 0 0 8px; font-size: 24px; }
      h2 { margin: 24px 0 8px; font-size: 16px; }
      p, li { line-height: 1.5; font-size: 13px; }
      .meta { color: #6B7280; font-size: 12px; margin-bottom: 18px; }
      .section { border-top: 1px solid #E5E7EB; padding-top: 16px; margin-top: 16px; }
    </style>
  </head>
  <body>
    <h1>${playbook.title}</h1>
    <div class="meta">${playbook.category} | ${playbook.brands.join(', ')} | Last updated ${playbook.lastUpdated}</div>
    <p>${playbook.description}</p>
    ${playbook.sections
      .map(
        (section) => `
          <div class="section">
            <h2>${section.title}</h2>
            <p>${section.content}</p>
            ${
              section.subsections?.length
                ? `<ul>${section.subsections
                    .map((subsection) => `<li><strong>${subsection.title}:</strong> ${subsection.content}</li>`)
                    .join('')}</ul>`
                : ''
            }
          </div>
        `,
      )
      .join('')}
    <script>
      window.onload = function () {
        window.print();
      };
    </script>
  </body>
</html>`;

    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const win = window.open(url, '_blank', 'noopener,noreferrer,width=1024,height=768');

    if (!win) {
      URL.revokeObjectURL(url);
      return;
    }

    const cleanup = () => URL.revokeObjectURL(url);
    win.addEventListener('beforeunload', cleanup, { once: true });
    window.setTimeout(cleanup, 5000);
  };

  const handleShare = async () => {
    const shareData = {
      title: playbook.title,
      text: buildPlaybookDocument(playbook),
    };

    try {
      if (navigator.share) {
        await navigator.share(shareData);
        return;
      }

      await navigator.clipboard.writeText(shareData.text);
    } catch {
      // Intentionally silent: share is a convenience action.
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-center bg-slate-950/60 px-0 py-0 sm:px-4 sm:py-6">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Close playbook detail overlay"
        onClick={onClose}
      />

      <div className="relative z-10 flex h-full w-full max-w-4xl flex-col overflow-hidden bg-white shadow-[0_30px_80px_rgba(15,23,42,0.18)] transition-all duration-300 sm:h-auto sm:max-h-[90vh] sm:rounded-3xl">
        <div className="flex items-start justify-between border-b border-gray-200 bg-slate-50 px-5 py-4 sm:px-7">
          <div className="pr-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${CATEGORY_TINTS[playbook.category].badge}`}>
                {playbook.category}
              </span>
              {playbook.brands.map((brand) => (
                <span
                  key={brand}
                  className="rounded-full border border-gray-200 bg-gray-100 px-3 py-1 text-xs font-medium text-slate-700"
                >
                  {brand}
                </span>
              ))}
            </div>
            <h2 className="text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">
              {playbook.title}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {playbook.description}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-slate-500 transition-colors hover:bg-white hover:text-slate-900"
            aria-label="Close playbook detail"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-7">
          <div className="grid gap-4 rounded-2xl border border-amber-100 bg-amber-50/60 p-4 sm:grid-cols-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Last updated
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {playbook.lastUpdated}
              </p>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Tags
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {playbook.tags.length}
              </p>
            </div>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Sections
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {playbook.sections.length}
              </p>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-500">
              <FileText className="h-4 w-4" />
              <span>Playbook Content</span>
            </div>

            {playbook.sections.length > 0 ? (
              playbook.sections.map((section) => {
                const isOpen = openSectionIds.includes(section.id);
                return (
                  <div
                    key={section.id}
                    className="overflow-hidden rounded-2xl border border-gray-200 bg-white"
                  >
                    <button
                      type="button"
                      onClick={() => toggleSection(section.id)}
                      className="flex w-full items-center justify-between gap-4 bg-slate-50 px-4 py-4 text-left transition-colors hover:bg-amber-50/60 sm:px-5"
                    >
                      <div>
                        <h3 className="text-sm font-semibold text-slate-900">
                          {section.title}
                        </h3>
                        <p className="mt-1 text-xs text-slate-500">
                          {isPlaybookExpandable(section)
                            ? 'Click to expand or collapse this section'
                            : 'Section content'}
                        </p>
                      </div>
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 text-amber-700" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-slate-400" />
                      )}
                    </button>

                    {isOpen && (
                      <div className="space-y-4 border-t border-gray-100 px-4 py-4 text-sm text-slate-700 sm:px-5">
                        <p className="leading-6">{section.content}</p>

                        {section.subsections?.length ? (
                          <div className="space-y-3">
                            {section.subsections.map((subsection) => (
                              <div
                                key={subsection.title}
                                className="rounded-xl border border-gray-200 bg-slate-50 p-4"
                              >
                                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                  {subsection.title}
                                </p>
                                <p className="mt-1.5 leading-6 text-slate-700">
                                  {subsection.content}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="rounded-2xl border border-dashed border-gray-200 bg-white px-4 py-6 text-sm text-slate-500">
                No detailed sections are attached to this playbook yet.
              </div>
            )}
          </div>
        </div>

        <div className="border-t border-gray-200 bg-slate-50 px-5 py-4 sm:px-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Clock3 className="h-4 w-4" />
              <span>Last updated: {playbook.lastUpdated}</span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleDownload}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-gray-50"
              >
                <Download className="h-4 w-4" />
                <span>Download PDF</span>
              </button>
              <button
                type="button"
                onClick={handleShare}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-gray-50"
              >
                <Share2 className="h-4 w-4" />
                <span>Share</span>
              </button>
              <button
                type="button"
                onClick={handlePrint}
                className="inline-flex items-center gap-2 rounded-xl border border-gray-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-gray-50"
              >
                <Printer className="h-4 w-4" />
                <span>Print</span>
              </button>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-amber-700"
              >
                <span>Close</span>
                <ArrowUpRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterSidebar({
  brands,
  categories,
  selectedBrands,
  selectedCategories,
  lastUpdatedRange,
  onToggleBrand,
  onToggleCategory,
  onChangeLastUpdatedRange,
  onResetFilters,
  brandCounts,
  categoryCounts,
}: {
  brands: string[];
  categories: PlaybookCategory[];
  selectedBrands: string[];
  selectedCategories: PlaybookCategory[];
  lastUpdatedRange: LastUpdatedFilter;
  onToggleBrand: (brand: string) => void;
  onToggleCategory: (category: PlaybookCategory) => void;
  onChangeLastUpdatedRange: (value: LastUpdatedFilter) => void;
  onResetFilters: () => void;
  brandCounts: Record<string, number>;
  categoryCounts: Record<PlaybookCategory, number>;
}) {
  return (
    <div className="h-full rounded-3xl border border-gray-200 bg-[#F9FAFB] p-5 text-slate-800 shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-200 pb-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Filter className="h-4 w-4 text-amber-600" />
          <span>Filter by</span>
        </div>
        <button
          type="button"
          onClick={onResetFilters}
          className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 transition-colors hover:text-amber-900"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          <span>Reset filters</span>
        </button>
      </div>

      <div className="mt-5 space-y-6">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Brand
            </h3>
            <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500 border border-gray-200">
              {brands.length}
            </span>
          </div>

          <div className="space-y-2">
            {brands.map((brand) => {
              const checked = selectedBrands.includes(brand);
              return (
                <label
                  key={brand}
                  className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm transition-colors ${
                    checked
                      ? 'border-amber-300 bg-amber-50 text-amber-900'
                      : 'border-transparent bg-white text-slate-700 hover:border-gray-200 hover:bg-white'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={`flex h-4 w-4 items-center justify-center rounded-[4px] border ${
                        checked ? 'border-amber-500 bg-amber-500' : 'border-gray-300 bg-white'
                      }`}
                    >
                      {checked ? <Check className="h-3 w-3 text-white" /> : null}
                    </span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggleBrand(brand)}
                      className="sr-only"
                    />
                    <span className={checked ? 'font-semibold' : 'font-medium'}>
                      {brand}
                    </span>
                  </span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                    {brandCounts[brand] ?? 0}
                  </span>
                </label>
              );
            })}
          </div>
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Category
            </h3>
            <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500 border border-gray-200">
              {categories.length}
            </span>
          </div>

          <div className="space-y-2">
            {categories.map((category) => {
              const checked = selectedCategories.includes(category);
              return (
                <label
                  key={category}
                  className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl border px-3 py-2 text-sm transition-colors ${
                    checked
                      ? 'border-amber-300 bg-amber-50 text-amber-900'
                      : 'border-transparent bg-white text-slate-700 hover:border-gray-200 hover:bg-white'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={`flex h-4 w-4 items-center justify-center rounded-[4px] border ${
                        checked ? 'border-amber-500 bg-amber-500' : 'border-gray-300 bg-white'
                      }`}
                    >
                      {checked ? <Check className="h-3 w-3 text-white" /> : null}
                    </span>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggleCategory(category)}
                      className="sr-only"
                    />
                    <span className={checked ? 'font-semibold' : 'font-medium'}>
                      {category}
                    </span>
                  </span>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                    {categoryCounts[category] ?? 0}
                  </span>
                </label>
              );
            })}
          </div>
        </section>

        <section>
          <h3 className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
            Last Updated
          </h3>

          <div className="space-y-2">
            {LAST_UPDATED_OPTIONS.map((option) => {
              const checked = lastUpdatedRange === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onChangeLastUpdatedRange(option.value)}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm transition-colors ${
                    checked
                      ? 'border-amber-300 bg-amber-50 text-amber-900'
                      : 'border-gray-200 bg-white text-slate-700 hover:bg-gray-50'
                  }`}
                >
                  <span className="font-medium">{option.label}</span>
                  <span className="text-[11px] font-semibold text-slate-500">
                    {checked ? 'Active' : ''}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

export const PlaybooksBrowser: React.FC<PlaybooksBrowserProps> = ({
  playbooks = [],
  filters,
  onSelectPlaybook,
}) => {
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<PlaybookCategory[]>([]);
  const [lastUpdatedRange, setLastUpdatedRange] = useState<LastUpdatedFilter>('all');
  const [isFilterDrawerOpen, setIsFilterDrawerOpen] = useState(false);
  const [activePlaybook, setActivePlaybook] = useState<PlaybookItem | null>(null);
  const [isDetailVisible, setIsDetailVisible] = useState(false);

  const availableBrands = useMemo(() => {
    const fallback = uniqueItems(playbooks.flatMap((playbook) => playbook.brands));
    return uniqueItems(filters?.brands?.length ? filters.brands : fallback);
  }, [filters?.brands, playbooks]);

  const availableCategories = useMemo<PlaybookCategory[]>(() => {
    const fallback = uniqueItems(playbooks.map((playbook) => playbook.category)) as PlaybookCategory[];
    return (filters?.categories?.length ? filters.categories : DEFAULT_CATEGORIES.filter((category) => fallback.includes(category))) as PlaybookCategory[];
  }, [filters?.categories, playbooks]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsFilterDrawerOpen(false);
        if (activePlaybook) {
          handleClosePlaybook();
        }
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [activePlaybook]);

  useEffect(() => {
    if (!activePlaybook && !isFilterDrawerOpen) {
      document.body.style.overflow = '';
      return;
    }

    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
    };
  }, [activePlaybook, isFilterDrawerOpen]);

  const handleToggleBrand = (brand: string) => {
    setSelectedBrands((current) =>
      current.includes(brand) ? current.filter((item) => item !== brand) : [...current, brand],
    );
  };

  const handleToggleCategory = (category: PlaybookCategory) => {
    setSelectedCategories((current) =>
      current.includes(category)
        ? current.filter((item) => item !== category)
        : [...current, category],
    );
  };

  const handleResetFilters = () => {
    setSelectedBrands([]);
    setSelectedCategories([]);
    setLastUpdatedRange('all');
  };

  const filteredPlaybooks = useMemo(() => {
    return playbooks.filter((playbook) => {
      const brandMatch =
        selectedBrands.length === 0 ||
        selectedBrands.some((brand) => playbook.brands.includes(brand));

      const categoryMatch =
        selectedCategories.length === 0 || selectedCategories.includes(playbook.category);

      const updatedMatch = matchesLastUpdated(playbook.lastUpdated, lastUpdatedRange);

      return brandMatch && categoryMatch && updatedMatch;
    });
  }, [lastUpdatedRange, playbooks, selectedBrands, selectedCategories]);

  const brandCounts = useMemo<Record<string, number>>(() => {
    return availableBrands.reduce<Record<string, number>>((acc, brand) => {
      acc[brand] = playbooks.filter((playbook) => {
        const categoryMatch =
          selectedCategories.length === 0 || selectedCategories.includes(playbook.category);
        const updatedMatch = matchesLastUpdated(playbook.lastUpdated, lastUpdatedRange);
        return playbook.brands.includes(brand) && categoryMatch && updatedMatch;
      }).length;
      return acc;
    }, {});
  }, [availableBrands, lastUpdatedRange, playbooks, selectedCategories]);

  const categoryCounts = useMemo<Record<PlaybookCategory, number>>(() => {
    return availableCategories.reduce<Record<PlaybookCategory, number>>((acc, category) => {
      acc[category] = playbooks.filter((playbook) => {
        const brandMatch =
          selectedBrands.length === 0 || selectedBrands.some((brand) => playbook.brands.includes(brand));
        const updatedMatch = matchesLastUpdated(playbook.lastUpdated, lastUpdatedRange);
        return playbook.category === category && brandMatch && updatedMatch;
      }).length;
      return acc;
    }, {} as Record<PlaybookCategory, number>);
  }, [availableCategories, lastUpdatedRange, playbooks, selectedBrands]);

  const handleSelectPlaybook = (playbook: PlaybookItem) => {
    setActivePlaybook(playbook);
    setIsDetailVisible(true);
    onSelectPlaybook?.(playbook);
  };

  const handleClosePlaybook = () => {
    setIsDetailVisible(false);
    window.setTimeout(() => {
      setActivePlaybook(null);
    }, 300);
  };

  const activeFilterCount = selectedBrands.length + selectedCategories.length + (lastUpdatedRange === 'all' ? 0 : 1);

  return (
    <section className="w-full text-slate-900">
      {playbooks.some((playbook) => playbook.autoGenerated) ? (
        <div className="mb-5 rounded-3xl border border-amber-200 bg-gradient-to-r from-amber-50 to-white px-5 py-4 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-amber-700">
                Auto-generated from decisions
              </p>
              <p className="mt-1 text-sm text-slate-700">
                Lens refreshes playbooks whenever a category reaches at least 10 approved decisions and flags contradictions for Brand Lead review.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
              <span className="rounded-full border border-amber-200 bg-amber-100 px-3 py-1 text-amber-900">
                Evidence-based
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-700">
                Phase 4 / Week 3
              </span>
            </div>
          </div>
        </div>
      ) : null}

      <div className="flex items-start gap-6">
        <aside className="hidden w-[240px] shrink-0 lg:block">
          <div className="sticky top-6">
            <FilterSidebar
              brands={availableBrands}
              categories={availableCategories}
              selectedBrands={selectedBrands}
              selectedCategories={selectedCategories}
              lastUpdatedRange={lastUpdatedRange}
              onToggleBrand={handleToggleBrand}
              onToggleCategory={handleToggleCategory}
              onChangeLastUpdatedRange={setLastUpdatedRange}
              onResetFilters={handleResetFilters}
              brandCounts={brandCounts}
              categoryCounts={categoryCounts}
            />
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="mb-4 flex items-center justify-between gap-3 lg:hidden">
            <button
              type="button"
              onClick={() => setIsFilterDrawerOpen(true)}
              className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:bg-gray-50"
            >
              <PanelsTopLeft className="h-4 w-4 text-amber-600" />
              <span>Filters</span>
              {activeFilterCount > 0 ? (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
                  {activeFilterCount}
                </span>
              ) : null}
            </button>

            <span className="text-xs font-medium text-slate-500">
              {filteredPlaybooks.length} matching playbooks
            </span>
          </div>

          <div className="mb-4 hidden items-center justify-between text-sm text-slate-600 lg:flex">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-900">
                {filteredPlaybooks.length}
              </span>
              <span>matching playbooks</span>
              {activeFilterCount > 0 ? (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-900">
                  {activeFilterCount} active filters
                </span>
              ) : null}
            </div>
            <button
              type="button"
              onClick={handleResetFilters}
              className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 transition-colors hover:text-amber-900"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset filters</span>
            </button>
          </div>

          {filteredPlaybooks.length > 0 ? (
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 xl:gap-6">
              {filteredPlaybooks.map((playbook) => {
                const tint = CATEGORY_TINTS[playbook.category];

                return (
                  <article
                    key={playbook.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSelectPlaybook(playbook)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        handleSelectPlaybook(playbook);
                      }
                    }}
                    className="group w-full max-w-[340px] cursor-pointer overflow-hidden rounded-3xl border border-[#E5E7EB] bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)] transition-all duration-300 hover:scale-[1.02] hover:shadow-[0_4px_12px_rgba(0,0,0,0.08)] focus:outline-none focus:ring-2 focus:ring-amber-500/70"
                  >
                    <div className={`flex items-start justify-between border-b border-gray-100 px-5 py-4 ${tint.header}`}>
                      <div className={`inline-flex rounded-2xl border px-3 py-2 ${tint.accent}`}>
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className="rounded-full bg-white/80 px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm">
                          {playbook.category}
                        </span>
                        {playbook.autoGenerated ? (
                          <span
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                              playbook.reviewStatus === 'needs_review'
                                ? 'bg-rose-100 text-rose-800'
                                : 'bg-emerald-100 text-emerald-800'
                            }`}
                          >
                            {playbook.reviewStatus === 'needs_review'
                              ? `Needs review · ${playbook.contradictionCount ?? 0} contradictions`
                              : `Auto-updated · ${playbook.evidenceCount ?? 0} decisions`}
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <div className="space-y-4 px-5 py-5">
                      <div>
                        <h3 className="text-[16px] font-semibold leading-6 text-slate-900">
                          {playbook.title}
                        </h3>
                        <p className="mt-2 text-[13px] leading-6 text-slate-500">
                          {playbook.description}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {playbook.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-lg border border-gray-200 bg-gray-100 px-2.5 py-1 text-[11px] font-medium text-slate-700"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>

                      <div className="flex items-center justify-between border-t border-gray-100 pt-4 text-xs text-slate-500">
                        <div className="flex items-center gap-2">
                          <Clock3 className="h-4 w-4 text-slate-400" />
                          <span>Last updated: {playbook.lastUpdated}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {playbook.evidenceCount ? (
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                              {playbook.evidenceCount} decisions
                            </span>
                          ) : null}
                          <ArrowUpRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="rounded-3xl border border-dashed border-gray-300 bg-white px-6 py-16 text-center shadow-sm">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
                <PanelsTopLeft className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">No results</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
                No playbooks match the current brand, category, and last updated filters.
                Try clearing one or more filters to bring results back.
              </p>
              <button
                type="button"
                onClick={handleResetFilters}
                className="mt-6 inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-amber-700"
              >
                <RotateCcw className="h-4 w-4" />
                <span>Reset filters</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {isFilterDrawerOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50"
            aria-label="Close filter drawer"
            onClick={() => setIsFilterDrawerOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 flex w-full max-w-sm flex-col bg-[#F9FAFB] shadow-2xl">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Filter className="h-4 w-4 text-amber-600" />
                <span>Filters</span>
              </div>
              <button
                type="button"
                onClick={() => setIsFilterDrawerOpen(false)}
                className="rounded-full p-2 text-slate-500 transition-colors hover:bg-white hover:text-slate-900"
                aria-label="Close filters"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              <FilterSidebar
                brands={availableBrands}
                categories={availableCategories}
                selectedBrands={selectedBrands}
                selectedCategories={selectedCategories}
                lastUpdatedRange={lastUpdatedRange}
                onToggleBrand={handleToggleBrand}
                onToggleCategory={handleToggleCategory}
                onChangeLastUpdatedRange={setLastUpdatedRange}
                onResetFilters={handleResetFilters}
                brandCounts={brandCounts}
                categoryCounts={categoryCounts}
              />
            </div>
          </div>
        </div>
      ) : null}

      {activePlaybook ? (
        <div
          className={`transition-opacity duration-300 ${
            isDetailVisible ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <PlaybookModal playbook={activePlaybook} onClose={handleClosePlaybook} />
        </div>
      ) : null}
    </section>
  );
};

export default PlaybooksBrowser;
