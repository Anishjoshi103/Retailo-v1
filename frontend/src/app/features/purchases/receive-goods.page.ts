import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { finalize, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { InventoryApi } from '../inventory/inventory.api';
import { ProductSummary } from '../inventory/inventory.models';
import { formatMoney, formatQuantity, formatRupees, lineGross, parseMoney, parseQuantity } from '../pos/money';
import { PurchasesApi } from './purchases.api';
import { PurchaseReceipt, ReceiveGoodsRequest, Supplier } from './purchases.models';

const MAX_SUPPLIER_NAME = 180;
const MAX_INVOICE_NUMBER = 80;

function newIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;
  return typeof cryptoApi?.randomUUID === 'function'
    ? cryptoApi.randomUUID()
    : `receipt-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

interface Line {
  readonly product: ProductSummary;
  readonly quantityText: string;
  readonly costText: string;
}

@Component({
  selector: 'app-receive-goods-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './receive-goods.page.html',
  styleUrl: './receive-goods.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReceiveGoodsPage {
  private readonly purchasesApi = inject(PurchasesApi);
  private readonly inventoryApi = inject(InventoryApi);
  private readonly session = inject(SessionContextService);

  readonly maxSupplierName = MAX_SUPPLIER_NAME;
  readonly maxInvoiceNumber = MAX_INVOICE_NUMBER;
  readonly rupees = formatRupees;

  readonly suppliers = signal<readonly Supplier[]>([]);
  readonly suppliersFailed = signal(false);
  /** Empty string means "no saved supplier; type a name instead". */
  readonly supplierId = signal('');
  readonly supplierName = signal('');
  readonly invoiceNumber = signal('');
  readonly lines = signal<readonly Line[]>([]);

  readonly search = signal('');
  readonly results = signal<readonly ProductSummary[]>([]);
  readonly searching = signal(false);
  readonly searchError = signal('');

  readonly submitting = signal(false);
  readonly submitError = signal('');
  readonly completed = signal<{ readonly receipt: PurchaseReceipt; readonly totalPaise: number } | null>(null);

  private attempt: { readonly key: string; readonly fingerprint: string } | null = null;

  readonly pricedLines = computed(() => this.lines().map((line) => {
    const quantityMilli = parseQuantity(line.quantityText);
    const costPaise = parseMoney(line.costText);
    const valid = quantityMilli !== null && costPaise !== null;
    return { line, quantityMilli, costPaise, valid, grossPaise: valid ? lineGross(costPaise, quantityMilli) : null };
  }));
  readonly linesValid = computed(() => this.pricedLines().length > 0 && this.pricedLines().every((priced) => priced.valid));
  readonly totalPaise = computed(() => this.pricedLines().reduce((sum, priced) => sum + (priced.grossPaise ?? 0), 0));

  readonly supplierValid = computed(() => this.supplierId() !== '' || (this.supplierName().trim().length > 0 && this.supplierName().trim().length <= MAX_SUPPLIER_NAME));
  readonly canSubmit = computed(() => !this.submitting() && !!this.session.selectedBranchId() && this.linesValid()
    && this.supplierValid() && this.invoiceNumber().trim().length <= MAX_INVOICE_NUMBER);

  constructor() {
    // Saved suppliers are optional: if they cannot be loaded the supplier can still be typed in.
    this.purchasesApi.suppliers({ active: true })
      .pipe(catchError(() => { this.suppliersFailed.set(true); return of([] as readonly Supplier[]); }))
      .subscribe((suppliers) => this.suppliers.set(suppliers));
  }

  chooseSupplier(id: string): void {
    this.supplierId.set(id);
    if (id !== '') this.supplierName.set('');
  }

  searchProducts(): void {
    const text = this.search().trim();
    if (!text) { this.results.set([]); return; }
    this.searching.set(true);
    this.searchError.set('');
    this.inventoryApi.searchProducts(text).pipe(finalize(() => this.searching.set(false))).subscribe({
      next: (products) => {
        // A scanner or exact SKU/barcode entry goes straight into the list.
        const exact = products.find((p) => p.barcode === text || p.sku.toLowerCase() === text.toLowerCase());
        if (exact) { this.addProduct(exact); this.search.set(''); this.results.set([]); return; }
        this.results.set(products);
      },
      error: () => { this.results.set([]); this.searchError.set('We could not search products. Try again.'); },
    });
  }

  addProduct(product: ProductSummary): void {
    const existing = this.lines().find((line) => line.product.id === product.id);
    if (existing) {
      this.setQuantity(product.id, formatQuantity((parseQuantity(existing.quantityText) ?? 0) + 1000));
      return;
    }
    this.lines.update((all) => [...all, { product, quantityText: '1', costText: '' }]);
    this.results.set([]);
  }

  setQuantity(productId: string, quantityText: string): void {
    this.lines.update((all) => all.map((line) => (line.product.id === productId ? { ...line, quantityText } : line)));
  }

  setCost(productId: string, costText: string): void {
    this.lines.update((all) => all.map((line) => (line.product.id === productId ? { ...line, costText } : line)));
  }

  removeLine(productId: string): void {
    this.lines.update((all) => all.filter((line) => line.product.id !== productId));
  }

  lineTotal(grossPaise: number | null): string {
    return grossPaise === null ? '—' : formatRupees(grossPaise);
  }

  submit(): void {
    const branchId = this.session.selectedBranchId();
    if (!branchId || !this.canSubmit()) return;
    const request = this.buildRequest(branchId);
    const fingerprint = JSON.stringify(request);
    // Same delivery -> same key, so a retry after a lost response can never add the stock twice.
    if (this.attempt?.fingerprint !== fingerprint) this.attempt = { key: newIdempotencyKey(), fingerprint };
    const total = this.totalPaise();
    this.submitting.set(true);
    this.submitError.set('');
    this.purchasesApi.receiveGoods(request, this.attempt.key).pipe(finalize(() => this.submitting.set(false))).subscribe({
      next: (receipt) => { this.attempt = null; this.completed.set({ receipt, totalPaise: total }); },
      error: (error: unknown) => this.submitError.set(this.describe(error)),
    });
  }

  receiveMore(): void {
    this.lines.set([]);
    this.supplierId.set('');
    this.supplierName.set('');
    this.invoiceNumber.set('');
    this.search.set('');
    this.results.set([]);
    this.submitError.set('');
    this.attempt = null;
    this.completed.set(null);
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  private buildRequest(branchId: string): ReceiveGoodsRequest {
    const invoice = this.invoiceNumber().trim();
    return {
      branch_id: branchId,
      ...(this.supplierId() !== '' ? { supplier_id: this.supplierId() } : { supplier_name: this.supplierName().trim() }),
      ...(invoice ? { supplier_invoice_number: invoice } : {}),
      lines: this.pricedLines().map((priced) => ({
        product_id: priced.line.product.id,
        quantity: formatQuantity(priced.quantityMilli as number),
        unit_cost: formatMoney(priced.costPaise as number),
      })),
    };
  }

  private describe(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Tap Receive goods again: the same delivery will not be added twice.';
      if (error.status === 403) return 'Only a manager, administrator or the owner can receive goods.';
      const details = Object.values(error.fieldErrors).flat();
      return details.length > 0 ? details.join(' ') : error.message;
    }
    return 'The delivery could not be saved. Please try again.';
  }
}
