import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { switchMap, tap } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { SalesApi } from '../pos/sales.api';
import { Sale } from '../pos/sales.models';

@Component({
  selector: 'app-invoice-detail-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './invoice-detail.page.html',
  styleUrl: './invoice-detail.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InvoiceDetailPage {
  private readonly salesApi = inject(SalesApi);
  private readonly route = inject(ActivatedRoute);

  readonly sale = signal<Sale | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly errorMessage = signal('');

  constructor() {
    this.route.paramMap
      .pipe(
        tap(() => { this.loading.set(true); this.sale.set(null); this.notFound.set(false); this.errorMessage.set(''); }),
        switchMap((params) => this.salesApi.get(params.get('id') ?? '')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe({ next: (sale) => { this.sale.set(sale); this.loading.set(false); }, error: (error: unknown) => this.fail(error) });
  }

  hasIgst(sale: Sale): boolean {
    return Number(sale.igst_total) !== 0;
  }

  print(): void {
    window.print();
  }

  private fail(error: unknown): void {
    this.loading.set(false);
    if (error instanceof ApiError && error.status === 404) this.notFound.set(true);
    else this.errorMessage.set('We could not load this invoice. Check your connection and try again.');
  }
}
