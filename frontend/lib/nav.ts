// Single source of truth for the five dashboards. The sidebar, the overview
// page and each route all read from here, so adding a sixth dashboard is a
// one-entry change.

export interface NavItem {
  slug: string;          // matches the API path AND the route path
  title: string;
  subtitle: string;
  headlineKpi: string;   // which KPI the overview card shows
}

export const DASHBOARDS: NavItem[] = [
  {
    slug: "inventory-analysis",
    title: "Inventory Analysis",
    subtitle: "What stock do we have, and is it healthy?",
    headlineKpi: "Total Stock Value",
  },
  {
    slug: "consumption",
    title: "Consumption",
    subtitle: "What is being used, by whom, where, and how it has trended.",
    headlineKpi: "Total Consumption Value",
  },
  {
    slug: "formulary-compliance",
    title: "Formulary Compliance",
    subtitle: "Is usage sticking to the approved item list?",
    headlineKpi: "Formulary Compliance",
  },
  {
    slug: "sob-opportunities",
    title: "SOB Opportunities",
    subtitle: "Where is vendor spend fragmented enough to consolidate?",
    headlineKpi: "Consolidation Opportunities",
  },
  {
    slug: "sob-compliance",
    title: "SOB Compliance",
    subtitle: "Are we honouring the agreed vendor commitments?",
    headlineKpi: "SOB Compliance",
  },
];
