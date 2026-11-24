import { ChangeDetectionStrategy, Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpParams } from '@angular/common/http';
import { finalize } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { ApiError } from '../../core/api/api-error.model';

interface Product {
  readonly id: string;
  readonly sku: string;
  readonly barcode: string | null;
  readonly name: string;
  readonly description?: string;
  readonly unit: string;
  readonly hsn_code: string;
  readonly gst_rate: string;
  readonly selling_price: string;
  readonly purchase_price: string;
  readonly is_active: boolean;
}

interface CreateProductRequest {
  readonly sku: string;
  readonly barcode: string | null;
  readonly name: string;
  readonly description: string;
  readonly unit: string;
  readonly hsn_code: string;
  readonly gst_rate: string;
  readonly selling_price: string;
  readonly purchase_price: string;
  readonly is_active: boolean;
}

interface ProductDraft {
  sku: string;
  barcode: string;
  name: string;
  description: string;
  unit: string;
  hsn_code: string;
  gst_rate: string;
  selling_price: string;
  purchase_price: string;
  is_active: boolean;
}

const EMPTY_DRAFT = (): ProductDraft => ({
  sku: '', barcode: '', name: '', description: '', unit: 'each',
  hsn_code: '', gst_rate: '0.00', selling_price: '0.00',
  purchase_price: '0.00', is_active: true,
});

const MONEY_PATTERN = /^\d{1,10}(\.\d{1,2})?$/;
const GST_PATTERN = /^\d{1,3}(\.\d{1,2})?$/;

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
  readonly formOpen = signal(false);
  readonly draft = signal<ProductDraft>(EMPTY_DRAFT());
  readonly saving = signal(false);
  readonly createError = signal('');
  readonly fieldErrors = signal<Readonly<Record<string, readonly string[]>>>({});
  readonly units = [
    { value: 'each', label: 'Each' }, { value: 'kg', label: 'Kilogram' },
    { value: 'g', label: 'Gram' }, { value: 'l', label: 'Litre' },
    { value: 'ml', label: 'Millilitre' }, { value: 'm', label: 'Metre' },
    { value: 'pack', label: 'Pack' },
  ] as const;

  readonly canCreate = computed(() => {
    const value = this.draft();
    const gst = value.gst_rate.trim();
    return !this.saving()
      && value.sku.trim().length > 0 && value.sku.trim().length <= 64
      && value.name.trim().length > 0 && value.name.trim().length <= 180
      && (!value.barcode.trim() || value.barcode.trim().length <= 64)
      && (!value.description.trim() || value.description.trim().length <= 500)
      && (!value.hsn_code.trim() || /^\d{4}(?:\d{2}){0,2}$/.test(value.hsn_code.trim()))
      && GST_PATTERN.test(gst) && Number(gst) >= 0 && Number(gst) <= 100
      && MONEY_PATTERN.test(value.selling_price.trim())
      && MONEY_PATTERN.test(value.purchase_price.trim());
  });

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

  openCreateForm(): void {
    this.draft.set(EMPTY_DRAFT());
    this.fieldErrors.set({});
    this.createError.set('');
    this.formOpen.set(true);
  }

  closeCreateForm(): void {
    if (this.saving()) return;
    this.formOpen.set(false);
    this.fieldErrors.set({});
    this.createError.set('');
  }

  updateDraft<K extends keyof ProductDraft>(field: K, value: ProductDraft[K]): void {
    this.draft.update((current) => ({ ...current, [field]: value }));
    this.fieldErrors.update((current) => ({ ...current, [field]: [] }));
    this.createError.set('');
  }

  createProduct(): void {
    if (!this.canCreate()) return;
    const value = this.draft();
    const request: CreateProductRequest = {
      sku: value.sku.trim().toUpperCase(),
      barcode: value.barcode.trim() || null,
      name: value.name.trim(),
      description: value.description.trim(),
      unit: value.unit,
      hsn_code: value.hsn_code.trim(),
      gst_rate: value.gst_rate.trim(),
      selling_price: value.selling_price.trim(),
      purchase_price: value.purchase_price.trim(),
      is_active: value.is_active,
    };
    this.saving.set(true);
    this.createError.set('');
    this.fieldErrors.set({});
    this.api.post<Product, CreateProductRequest>('products', request)
      .pipe(finalize(() => this.saving.set(false)))
      .subscribe({
        next: (created) => {
          this.formOpen.set(false);
          this.draft.set(EMPTY_DRAFT());
          this.products.update((items) => [created, ...items]);
          this.loadProducts();
        },
        error: (error: unknown) => {
          if (error instanceof ApiError) {
            this.fieldErrors.set(error.fieldErrors);
            this.createError.set(error.status === 0
              ? 'We could not reach the server. Check your connection and try again.'
              : error.message || 'The product could not be saved. Review the fields and try again.');
          } else {
            this.createError.set('The product could not be saved. Please try again.');
          }
        },
      });
  }

  fieldError(field: string): string {
    return this.fieldErrors()[field]?.join(' ') ?? '';
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
