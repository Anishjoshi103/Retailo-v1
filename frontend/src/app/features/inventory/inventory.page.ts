import { ChangeDetectionStrategy, Component, computed, effect, inject, signal, untracked } from '@angular/core';
import { finalize } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { formatSignedQuantity, parseQuantityOrZero, parseSignedQuantity } from '../pos/money';
import { InventoryApi } from './inventory.api';
import { AdjustStockRequest, ProductSummary, StockBalance } from './inventory.models';

const ADJUSTING_ROLES: readonly string[] = ['owner', 'admin', 'manager'];
const MAX_NOTE_LENGTH = 500;

export const ADJUSTMENT_REASONS: readonly string[] = ['Stock take', 'Damaged', 'Expired', 'Found stock', 'Correction'];

function newIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;
  return typeof cryptoApi?.randomUUID === 'function'
    ? cryptoApi.randomUUID()
    : `adjust-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

type Filter = 'all' | 'attention';
type Mode = 'count' | 'change';
type StockStatus = 'ok' | 'zero' | 'negative';

interface Row {
  readonly balance: StockBalance;
  readonly onHandMilli: number;
  readonly status: StockStatus;
}

interface Target {
  readonly productId: string;
  readonly sku: string;
  readonly name: string;
  readonly onHandMilli: number;
}

@Component({
  selector: 'app-inventory-page',
  standalone: true,
  templateUrl: './inventory.page.html',
  styleUrl: './inventory.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InventoryPage {
  private readonly inventoryApi = inject(InventoryApi);
  private readonly session = inject(SessionContextService);

  readonly reasons = ADJUSTMENT_REASONS;
  readonly maxNoteLength = MAX_NOTE_LENGTH;
  readonly formatSigned = formatSignedQuantity;

  readonly balances = signal<readonly StockBalance[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal('');
  readonly search = signal('');
  readonly filter = signal<Filter>('all');
  readonly notice = signal('');

  readonly canAdjust = computed(() => this.session.roles().some((role) => ADJUSTING_ROLES.includes(role)));

  readonly rows = computed<readonly Row[]>(() => this.balances()
    .map((balance) => {
      const onHandMilli = parseSignedQuantity(balance.quantity_on_hand) ?? 0;
      const status: StockStatus = onHandMilli < 0 ? 'negative' : onHandMilli === 0 ? 'zero' : 'ok';
      return { balance, onHandMilli, status };
    })
    .sort((a, b) => a.balance.product_name.localeCompare(b.balance.product_name)));

  readonly attentionCount = computed(() => this.rows().filter((row) => row.status !== 'ok').length);
  readonly negativeCount = computed(() => this.rows().filter((row) => row.status === 'negative').length);

  readonly visibleRows = computed(() => {
    const text = this.search().trim().toLowerCase();
    return this.rows().filter((row) =>
      (this.filter() === 'all' || row.status !== 'ok')
      && (!text || row.balance.product_name.toLowerCase().includes(text) || row.balance.product_sku.toLowerCase().includes(text)));
  });

  // Adjusting
  readonly target = signal<Target | null>(null);
  readonly mode = signal<Mode>('count');
  readonly countedText = signal('');
  readonly changeText = signal('');
  readonly reason = signal('');
  readonly submitting = signal(false);
  readonly adjustError = signal('');

  // Choosing a product that has no stock record yet
  readonly productSearch = signal('');
  readonly productResults = signal<readonly ProductSummary[]>([]);
  readonly searchingProducts = signal(false);
  readonly productSearchError = signal('');

  private attempt: { readonly key: string; readonly fingerprint: string } | null = null;

  /** The change to apply, in milli-units; null while the entered number is missing or invalid. */
  readonly delta = computed<number | null>(() => {
    const target = this.target();
    if (!target) return null;
    if (this.mode() === 'count') {
      const counted = parseQuantityOrZero(this.countedText());
      return counted === null ? null : counted - target.onHandMilli;
    }
    return parseSignedQuantity(this.changeText());
  });

  readonly newOnHandMilli = computed<number | null>(() => {
    const target = this.target();
    const delta = this.delta();
    return target && delta !== null ? target.onHandMilli + delta : null;
  });

  readonly inputError = computed(() => {
    const text = this.mode() === 'count' ? this.countedText() : this.changeText();
    if (text.trim() === '' || this.delta() !== null) return '';
    return this.mode() === 'count'
      ? 'Enter the counted quantity as a number of zero or more, with up to 3 decimals.'
      : 'Enter a change such as 5 or -2.5, with up to 3 decimals.';
  });

  readonly reasonValid = computed(() => this.reason().trim().length > 0 && this.reason().trim().length <= MAX_NOTE_LENGTH);
  readonly canSubmit = computed(() => !this.submitting() && this.delta() !== null && this.delta() !== 0 && this.reasonValid());

  constructor() {
    // Reload whenever the branch changes.
    effect(() => {
      this.session.selectedBranchId();
      untracked(() => this.load());
    });
  }

  load(): void {
    const branchId = this.session.selectedBranchId();
    if (!branchId) { this.balances.set([]); this.loading.set(false); return; }
    this.loading.set(true);
    this.loadError.set('');
    this.inventoryApi.balances(branchId).subscribe({
      next: (balances) => { this.balances.set(balances); this.loading.set(false); },
      error: () => { this.loadError.set('We could not load your stock. Check your connection and try again.'); this.loading.set(false); },
    });
  }

  quantity(row: Row): string {
    return formatSignedQuantity(row.onHandMilli);
  }

  // ---- adjusting
  adjust(row: Row): void {
    this.startAdjust({ productId: row.balance.product, sku: row.balance.product_sku, name: row.balance.product_name, onHandMilli: row.onHandMilli });
  }

  adjustProduct(product: ProductSummary): void {
    const existing = this.rows().find((row) => row.balance.product === product.id);
    this.startAdjust({ productId: product.id, sku: product.sku, name: product.name, onHandMilli: existing?.onHandMilli ?? 0 });
    this.productSearch.set('');
    this.productResults.set([]);
  }

  cancelAdjust(): void {
    this.target.set(null);
    this.adjustError.set('');
    this.attempt = null;
  }

  setMode(mode: Mode): void {
    this.mode.set(mode);
    this.adjustError.set('');
  }

  searchProducts(): void {
    const text = this.productSearch().trim();
    if (!text) { this.productResults.set([]); return; }
    this.searchingProducts.set(true);
    this.productSearchError.set('');
    this.inventoryApi.searchProducts(text).pipe(finalize(() => this.searchingProducts.set(false))).subscribe({
      next: (products) => this.productResults.set(products),
      error: () => { this.productResults.set([]); this.productSearchError.set('We could not search products. Try again.'); },
    });
  }

  submit(): void {
    const target = this.target();
    const branchId = this.session.selectedBranchId();
    const delta = this.delta();
    if (!target || !branchId || delta === null || !this.canSubmit()) return;
    const request: AdjustStockRequest = {
      branch_id: branchId, product_id: target.productId, quantity_delta: formatSignedQuantity(delta), note: this.reason().trim(),
    };
    const fingerprint = JSON.stringify(request);
    // Same adjustment -> same key, so a retry after a lost response can never apply it twice.
    if (this.attempt?.fingerprint !== fingerprint) this.attempt = { key: newIdempotencyKey(), fingerprint };
    this.submitting.set(true);
    this.adjustError.set('');
    this.inventoryApi.adjust(request, this.attempt.key).pipe(finalize(() => this.submitting.set(false))).subscribe({
      next: (result) => {
        this.attempt = null;
        this.applyResult(target, result.quantity_on_hand);
        this.notice.set(`${target.name}: stock is now ${formatSignedQuantity(parseSignedQuantity(result.quantity_on_hand) ?? 0)}.`);
        this.target.set(null);
      },
      error: (error: unknown) => this.adjustError.set(this.describe(error)),
    });
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  private startAdjust(target: Target): void {
    this.target.set(target);
    this.mode.set('count');
    this.countedText.set('');
    this.changeText.set('');
    this.reason.set('');
    this.adjustError.set('');
    this.notice.set('');
    this.attempt = null;
  }

  private applyResult(target: Target, quantityOnHand: string): void {
    const now = new Date().toISOString();
    this.balances.update((all) => all.some((item) => item.product === target.productId)
      ? all.map((item) => (item.product === target.productId ? { ...item, quantity_on_hand: quantityOnHand, updated_at: now } : item))
      : [...all, { id: `new-${target.productId}`, branch: this.session.selectedBranchId() ?? '', product: target.productId, product_sku: target.sku, product_name: target.name, quantity_on_hand: quantityOnHand, updated_at: now }]);
  }

  private describe(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Tap Save adjustment again: the same change will not be applied twice.';
      if (error.status === 403) return 'Only a manager, administrator or the owner can adjust stock.';
      const details = Object.values(error.fieldErrors).flat();
      return details.length > 0 ? details.join(' ') : error.message;
    }
    return 'The adjustment could not be saved. Please try again.';
  }
}
