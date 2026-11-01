import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpParams } from '@angular/common/http';
import { finalize } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';

interface Product {
  readonly id: string;
  readonly sku: string;
  readonly barcode: string | null;
  readonly name: string;
  readonly unit: string;
  readonly hsn_code: string;
  readonly gst_rate: string;
  readonly selling_price: string;
  readonly purchase_price: string;
  readonly is_active: boolean;
}

@Component({
  selector: 'app-catalog-page',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './catalog.page.html',
  styleUrl: './catalog.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CatalogPage implements OnInit {
  private readonly api = inject(ApiClient);

  readonly products = signal<readonly Product[]>([]);
  readonly searchText = signal('');
  readonly activeFilter = signal<'all' | 'active'>('all');
  readonly loading = signal(false);
  readonly errorMessage = signal('');

  ngOnInit(): void {
    this.loadProducts();
  }

  loadProducts(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    let params = new HttpParams();
    const search = this.searchText().trim();
    if (search) params = params.set('search', search);
    if (this.activeFilter() === 'active') params = params.set('active', 'true');

    this.api.get<readonly Product[]>('products', { params })
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (products) => this.products.set(products),
        error: () => {
          this.products.set([]);
          this.errorMessage.set('We could not load products. Check your connection and try again.');
        },
      });
  }

  submitSearch(): void {
    this.loadProducts();
  }

  setActiveFilter(value: string): void {
    this.activeFilter.set(value === 'active' ? 'active' : 'all');
    this.loadProducts();
  }

  trackProduct(_index: number, product: Product): string {
    return product.id;
  }
}
