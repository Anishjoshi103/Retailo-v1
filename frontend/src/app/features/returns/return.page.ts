import { ChangeDetectionStrategy, Component, computed, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { finalize, switchMap, tap } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { formatMoney, formatQuantity, formatRupees, parseMoney, parseQuantity } from '../pos/money';
import { SalesApi } from '../pos/sales.api';
import { Sale, SaleLineView } from '../pos/sales.models';
import { previewReturn, returnableMilli, ReturnLineInput } from './return-math';
import { ReturnsApi } from './returns.api';
import { CreateReturnRequest } from './returns.models';

const MAX_REASON_LENGTH = 200;

export const QUICK_REASONS: readonly string[] = ['Damaged', 'Wrong item', 'Customer changed mind', 'Expired'];

function newIdempotencyKey(): string {
  const cryptoApi = globalThis.crypto;
  return typeof cryptoApi?.randomUUID === 'function'
    ? cryptoApi.randomUUID()
    : `return-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

interface LineState {
  readonly line: SaleLineView;
  readonly soldMilli: number;
  readonly returnedMilli: number;
  readonly returnableMilli: number;
  readonly text: string;
  /** Parsed quantity to return (milli-units), or null when empty or invalid. */
  readonly quantityMilli: number | null;
  readonly error: string;
}

@Component({
  selector: 'app-return-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './return.page.html',
  styleUrl: './return.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReturnPage {
  private readonly salesApi = inject(SalesApi);
  private readonly returnsApi = inject(ReturnsApi);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly quickReasons = QUICK_REASONS;
  readonly maxReasonLength = MAX_REASON_LENGTH;
  readonly sale = signal<Sale | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly loadError = signal('');
  readonly quantities = signal<Readonly<Record<string, string>>>({});
  readonly reason = signal('');
  readonly submitting = signal(false);
  readonly submitError = signal('');

  private attempt: { readonly key: string; readonly fingerprint: string } | null = null;

  readonly lines = computed<readonly LineState[]>(() => (this.sale()?.lines ?? []).map((line) => {
    const soldMilli = parseQuantity(line.quantity) ?? 0;
    const returnedMilli = Math.round(Number(line.returned_quantity) * 1000);
    const remaining = returnableMilli(soldMilli, returnedMilli);
    const text = this.quantities()[line.id] ?? '';
    const parsed = text.trim() === '' ? null : parseQuantity(text);
    let error = '';
    if (text.trim() !== '' && parsed === null) error = 'Enter a quantity above zero, with up to 3 decimals.';
    else if (parsed !== null && parsed > remaining) error = `Only ${formatQuantity(remaining)} can still be returned.`;
    return { line, soldMilli, returnedMilli, returnableMilli: remaining, text, quantityMilli: parsed, error };
  }));

  readonly anythingReturnable = computed(() => this.lines().some((state) => state.returnableMilli > 0));
  private readonly selected = computed(() => this.lines().filter((state) => state.quantityMilli !== null && state.error === ''));
  readonly hasErrors = computed(() => this.lines().some((state) => state.error !== ''));

  readonly preview = computed(() => previewReturn(this.selected().map((state): ReturnLineInput => ({
    soldMilli: state.soldMilli,
    returnedBeforeMilli: state.returnedMilli,
    quantityMilli: state.quantityMilli as number,
    taxablePaise: parseMoney(state.line.taxable_value) ?? 0,
    cgstPaise: parseMoney(state.line.cgst_amount) ?? 0,
    sgstPaise: parseMoney(state.line.sgst_amount) ?? 0,
    igstPaise: parseMoney(state.line.igst_amount) ?? 0,
  }))));

  readonly reasonValid = computed(() => this.reason().trim().length > 0 && this.reason().trim().length <= MAX_REASON_LENGTH);
  readonly canSubmit = computed(() =>
    !this.submitting() && !this.hasErrors() && this.selected().length > 0 && this.reasonValid());

  readonly money = formatMoney;
  readonly rupees = formatRupees;

  constructor() {
    this.route.paramMap
      .pipe(
        tap(() => { this.loading.set(true); this.sale.set(null); this.notFound.set(false); this.loadError.set(''); this.quantities.set({}); }),
        switchMap((params) => this.salesApi.get(params.get('id') ?? '')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe({
        next: (sale) => { this.sale.set(sale); this.loading.set(false); },
        error: (error: unknown) => {
          this.loading.set(false);
          if (error instanceof ApiError && error.status === 404) this.notFound.set(true);
          else this.loadError.set('We could not load this invoice. Check your connection and try again.');
        },
      });
  }

  inputValue(event: Event): string {
    return (event.target as HTMLInputElement).value;
  }

  setQuantity(lineId: string, text: string): void {
    this.quantities.update((current) => ({ ...current, [lineId]: text }));
  }

  returnAll(state: LineState): void {
    if (state.returnableMilli > 0) this.setQuantity(state.line.id, formatQuantity(state.returnableMilli));
  }

  returnEverything(): void {
    this.quantities.set(Object.fromEntries(this.lines().filter((s) => s.returnableMilli > 0).map((s) => [s.line.id, formatQuantity(s.returnableMilli)])));
  }

  clearQuantities(): void {
    this.quantities.set({});
  }

  setReason(text: string): void {
    this.reason.set(text);
  }

  submit(): void {
    const sale = this.sale();
    if (!sale || !this.canSubmit()) return;
    const request = this.buildRequest();
    const fingerprint = JSON.stringify([sale.id, request]);
    // Same return -> same key, so a retry after a lost response can never refund or restock twice.
    if (this.attempt?.fingerprint !== fingerprint) this.attempt = { key: newIdempotencyKey(), fingerprint };
    this.submitting.set(true);
    this.submitError.set('');
    this.returnsApi.create(sale.id, request, this.attempt.key)
      .pipe(finalize(() => this.submitting.set(false)))
      .subscribe({
        next: (note) => { this.attempt = null; void this.router.navigate(['/gst/credit-notes', note.id]); },
        error: (error: unknown) => this.submitError.set(this.describeError(error)),
      });
  }

  private buildRequest(): CreateReturnRequest {
    return {
      reason: this.reason().trim(),
      lines: this.selected().map((state) => ({ sale_line_id: state.line.id, quantity: formatQuantity(state.quantityMilli as number) })),
    };
  }

  private describeError(error: unknown): string {
    if (error instanceof ApiError) {
      if (error.status === 0) return 'We could not reach the server. Tap Issue credit note again: the same return will not be refunded twice.';
      const details = Object.values(error.fieldErrors).flat();
      return details.length > 0 ? details.join(' ') : error.message;
    }
    return 'The return could not be completed. Please try again.';
  }
}
