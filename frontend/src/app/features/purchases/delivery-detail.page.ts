import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { switchMap, tap } from 'rxjs';
import { ApiError } from '../../core/api/api-error.model';
import { PurchasesApi } from './purchases.api';
import { ReceiptDetail } from './purchases.models';

@Component({
  selector: 'app-delivery-detail-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './delivery-detail.page.html',
  styleUrl: './delivery-detail.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DeliveryDetailPage {
  private readonly purchasesApi = inject(PurchasesApi);
  private readonly route = inject(ActivatedRoute);

  readonly delivery = signal<ReceiptDetail | null>(null);
  readonly loading = signal(true);
  readonly notFound = signal(false);
  readonly errorMessage = signal('');

  constructor() {
    this.route.paramMap
      .pipe(
        tap(() => { this.loading.set(true); this.delivery.set(null); this.notFound.set(false); this.errorMessage.set(''); }),
        switchMap((params) => this.purchasesApi.receipt(params.get('id') ?? '')),
        takeUntilDestroyed(inject(DestroyRef)),
      )
      .subscribe({
        next: (delivery) => { this.delivery.set(delivery); this.loading.set(false); },
        error: (error: unknown) => {
          this.loading.set(false);
          if (error instanceof ApiError && error.status === 404) this.notFound.set(true);
          else this.errorMessage.set('We could not load this delivery. Check your connection and try again.');
        },
      });
  }

  day(iso: string): string {
    return iso.slice(0, 10);
  }
}
