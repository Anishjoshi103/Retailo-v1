export interface PlannedModule {
  readonly number: string;
  readonly name: string;
  readonly description: string;
}

export const PLANNED_MODULES: readonly PlannedModule[] = [
  {
    number: '01',
    name: 'Point of sale',
    description: 'A fast, cashier-friendly checkout flow.'
  },
  {
    number: '02',
    name: 'Inventory',
    description: 'Stock levels, movements and adjustments.'
  },
  {
    number: '03',
    name: 'GST & reports',
    description: 'Tax-ready records and business insights.'
  }
];
