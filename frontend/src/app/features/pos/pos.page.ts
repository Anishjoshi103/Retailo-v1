import { HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';
import { formatMoney, formatQuantity, formatRupees, lineGross, parseMoney, parseQuantity, priceCart } from './money';
import { SalesApi } from './sales.api';
import { CreateSaleRequest, PaymentMethod, Sale } from './sales.models';

interface Product {
  readonly id: string;
  readonly sku: string;
  readonly barcode: string | null;
  readonly name: string;
  readonly unit: string;
  readonly gst_rate: string;
  /** Tax-inclusive (MRP-style) selling price. */
  readonly selling_price: string;
  readonly is_active: boolean;
}

interface CartItem {
  readonly product: Product;
  readonly quantityText: string;
}

interface PaymentRow {
  readonly id: number;
  readonly method: PaymentMethod;
  readonly amountText: string;
  readonly reference: string;
}

const STOCK_OVERRIDE_ROLES: readonly string[] = ['owner', 'admin', 'manager'];

function newIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;
  return typeof cryptoApi?.randomUUID === 'function'
    ? cryptoApi.randomUUID()
    : `sale-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

@Component({
  selector: 'app-pos-page',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './pos.page.html',
  styleUrl: './pos.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PosPage {
  private readonly api = inject(ApiClient);
  private readonly salesApi = inject(SalesApi);
  private readonly session = inject(SessionContextService);

  readonly paymentMethods: readonly { readonly value: PaymentMethod; readonly label: string }[] = [
    { value: 'cash', label: 'Cash' },
    { value: 'upi', label: 'UPI' },
    { value: 'card', label: 'Card' },
    { value: 'other', label: 'Other' },
  ];

  readonly searchText = signal('');
  readonly results = signal<readonly Product[]>([]);
  readonly searching = signal(false);
  readonly searchError = signal('');
  readonly cart = signal<readonly CartItem[]>([]);
  readonly customerName = signal('');
  readonly allowBelowStock = signal(false);
  readonly payments = signal<readonly PaymentRow[]>([this.blankPayment(1)]);
  readonly submitting = signal(false);
  readonly submitError = signal('');
  readonly completedSale = signal<Sale | null>(null);

  private nextPaymentId = 2;
  private autoFillPayment = true;
  private attempt: { readonly key: string; readonly fingerprint: string } | null = null;

  readonly canOverrideStock = computed(() => this.session.roles().some((role) => STOCK_OVERRIDE_ROLES.includes(role)));

  /** Cart lines with parsed quantity and exact gross amount; invalid quantities are flagged. */
  readonly pricedItems = computed(() => this.cart().map((item) => {
    const pricePaise = parseMoney(item.product.selling_price);
    const quantityMilli = parseQuantity(item.quantityText);
    const valid = pricePaise !== null && quantityMilli !== null;
    return { item, pricePaise, quantityMilli, valid, grossPaise: valid ? lineGross(pricePaise, quantityMilli) : null };
  }));
  readonly cartValid = computed(() => this.pricedItems().length > 0 && this.pricedItems().every((line) => line.valid));
  readonly totals = computed(() => priceCart(this.pricedItems().flatMap((line) =>
    line.valid ? [{ pricePaise: line.pricePaise as number, quantityMilli: line.quantityMilli as number }] : [])));

  readonly paymentsPaise = computed(() => this.payments().map((row) => parseMoney(row.amountText)));
  readonly paymentsValid = computed(() => this.paymentsPaise().every((value) => value !== null && value > 0));
  readonly paidPaise = computed(() => this.paymentsPaise().reduce<number>((sum, value) => sum + (value ?? 0), 0));
  readonly remainingPaise = computed(() => this.totals().grandTotalPaise - this.paidPaise());
  readonly canSubmit = computed(() =>
    !this.submitting() && !!this.session.selectedBranchId() && this.cartValid() && this.totals().grandTotalPaise > 0
    && this.paymentsValid() && this.remainingPaise() === 0);

  readonly money = formatMoney;
  readonly rupees = formatRupees;

  search(): void {
    const text = this.searchText().trim();
    if (!text) { this.results.set([]); return; }
    this.searching.set(true);
    this.searchError.set('');
    const params = new HttpParams().set('search', text).set('active', 'true');
    this.api.get<readonly Product[]>('products', { params })
      .pipe(finalize(() => this.searching.set(false)))
      .subscribe({
        next: (products) => {
          // A scanner or exact SKU/barcode entry goes straight into the cart.
          const lowered = text.toLowerCase();
          const exact = products.find((p) => p.barcode === text || p.sku.toLowerCase() === lowered);
          if (exact) { this.addProduct(exact); this.searchText.set(''); this.results.set([]); return; }
          this.results.set(products);
        },
        error: () => { this.results.set([]); this.searchError.set('We could not search products. Check your connection and try again.'); },
      });
  }

  addProduct(product: Product): void {
    const existing = this.cart().find((item) => item.product.id === product.id);
    if (existing) {
      const milli = parseQuantity(existing.quantityText);
      this.setQuantity(product.id, formatQuantity((milli ?? 0) + 1000));
      return;
    }
    this.cart.update((items) => [...items, { product, quantityText: '1' }]);
    this.cartChanged();
  }

  setQuantity(productId: string, quantityText: string): void {
    this.cart.update((items) => items.map((item) => (item.product.id === productId ? { ...item, quantityText } : item)));
    this.cartChanged();
  }

  removeItem(productId: string): void {
    this.cart.update((items) => items.filter((item) => item.product.id !== productId));
    this.cartChanged();
  }

  setPaymentMethod(id: number, method: string): void {
    const known = this.paymentMethods.find((item) => item.value === method);
    if (known) this.updatePayment(id, { method: known.value });
  }

  setPaymentAmount(id: number, amountText: string): void {
    this.autoFillPayment = false;
    this.updatePayment(id, { amountText });
  }

  setPaymentReference(id: number, reference: string): void {
    this.updatePayment(id, { reference });
  }

  addPayment(): void {
    this.autoFillPayment = false;
    const remaining = this.remainingPaise();
    this.payments.update((rows) => [...rows, { ...this.blankPayment(this.nextPaymentId++), amountText: remaining > 0 ? formatMoney(remaining) : '' }]);
  }

  removePayment(id: number): void {
    if (this.payments().length <= 1) return;
    this.payments.update((rows) => rows.filter((row) => row.id !== id));
  }

  submit(): void {
    const branchId = this.session.selectedBranchId();
    if (!this.canSubmit() || !branchId) return;
    const request = this.buildRequest(branchId);
    const fingerprint = JSON.stringify(request);
    // Same sale -> same key, so a retry after a lost response can never bill twice.
    if (this.attempt?.fingerprint !== fingerprint) this.attempt = { key: newIdempotencyKey(), fingerprint };
    this.submitting.set(true);
    this.submitError.set('');
    this.salesApi.create(request, this.attempt.key)
      .pipe(finalize(() => this.submitting.set(false)))
      .subscribe({
        next: (sale) => { this.completedSale.set(sale); this.attempt = null; },
        error: (error: unknown) => this.submitError.set(this.describeError(error)),
      });
  }

  newSale(): void {
    this.cart.set([]);
    this.customerName.set('');
    this.allowBelowStock.set(false);
    this.payments.set([this.blankPayment(1)]);
    this.nextPaymentId = 2;
    this.autoFillPayment = true;
    this.attempt = null;
    this.submitError.set('');
    this.completedSale.set(null);
    this.searchText.set('');
    this.results.set([]);
  }

  lineTotal(grossPaise: number | null): string {
    return grossPaise === null ? '—' : formatMoney(grossPaise);
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  private buildRequest(branchId: string): CreateSaleRequest {
    const customer = this.customerName().trim();
    return {
      branch_id: branchId,
      ...(customer ? { customer_name: customer } : {}),
      ...(this.canOverrideStock() && this.allowBelowStock() ? { allow_negative_stock: true } : {}),
      lines: this.pricedItems().map((line) => ({
        product_id: line.item.product.id,
        quantity: formatQuantity(line.quantityMilli as number),
      })),
      payments: this.payments().map((row, index) => ({
        method: row.method,
        amount: formatMoney(this.paymentsPaise()[index] as number),
        ...(row.reference.trim() ? { reference: row.reference.trim() } : {}),
      })),
    };
  }

  private cartChanged(): void {
    if (this.autoFillPayment && this.payments().length === 1) {
      const total = this.totals().grandTotalPaise;
      this.updatePayment(this.payments()[0].id, { amountText: total > 0 ? formatMoney(total) : '' });
    }
  }

  private updatePayment(id: number, change: Partial<PaymentRow>): void {
    this.payments.update((rows) => rows.map((row) => (row.id === id ? { ...row, ...change } : row)));
  }

  private blankPayment(id: number): PaymentRow {
    return { id, method: 'cash', amountText: '', reference: '' };
  }

  private describeError(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Tap Complete sale again: the same sale will not be billed twice.';
      const details = Object.values(error.fieldErrors).flat();
      return details.length > 0 ? details.join(' ') : error.message;
    }
    return 'The sale could not be completed. Please try again.';
  }
}
