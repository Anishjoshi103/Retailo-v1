import { provideHttpClient } from '@angular/common/http';
import { HttpParams } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { ApiError } from '../../core/api/api-error.model';
import { CatalogPage } from './catalog.page';

describe('CatalogPage', () => {
  let fixture: ComponentFixture<CatalogPage>;
  let api: { get: ReturnType<typeof vi.fn>; post: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    api = { get: vi.fn().mockReturnValue(of([])), post: vi.fn() };
    TestBed.configureTestingModule({
      imports: [CatalogPage],
      providers: [
        provideHttpClient(),
        { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api' } },
        { provide: ApiClient, useValue: api },
      ],
    });
    fixture = TestBed.createComponent(CatalogPage);
  });

  it('loads products from the tenant-scoped API endpoint', () => {
    fixture.detectChanges();
    expect(api.get).toHaveBeenCalledWith('products', expect.objectContaining({ params: expect.any(HttpParams) }));
    expect(fixture.nativeElement.textContent).toContain('No products found');
  });

  it('renders returned product details without converting decimal strings to numbers', () => {
    api.get.mockReturnValue(of([{
      id: 'p-1', sku: 'MILK-1', barcode: null, name: 'Milk', unit: 'each',
      hsn_code: '0401', gst_rate: '5.00', selling_price: '42.50',
      purchase_price: '35.00', is_active: true,
    }]));
    fixture.detectChanges();
    fixture.componentInstance.loadProducts();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Milk');
    expect(fixture.nativeElement.textContent).toContain('₹42.50');
    expect(fixture.nativeElement.textContent).toContain('5.00%');
  });

  it('opens the create form and requires the core product fields', () => {
    fixture.detectChanges();
    const page = fixture.componentInstance;
    page.openCreateForm();
    expect(page.formOpen()).toBe(true);
    expect(page.canCreate()).toBe(false);
    page.updateDraft('sku', 'milk-1');
    page.updateDraft('name', 'Milk');
    page.updateDraft('gst_rate', '5.00');
    page.updateDraft('selling_price', '42.50');
    page.updateDraft('purchase_price', '35.00');
    expect(page.canCreate()).toBe(true);
  });

  it('posts normalized product fields and refreshes the catalogue after creation', () => {
    const created = {
      id: 'p-2', sku: 'MILK-1', barcode: null, name: 'Milk',
      unit: 'each', hsn_code: '0401', gst_rate: '5.00',
      selling_price: '42.50', purchase_price: '35.00', is_active: true,
    };
    api.post.mockReturnValue(of(created));
    fixture.detectChanges();
    const page = fixture.componentInstance;
    page.openCreateForm();
    page.updateDraft('sku', ' milk-1 ');
    page.updateDraft('name', ' Milk ');
    page.updateDraft('hsn_code', '0401');
    page.updateDraft('gst_rate', '5.00');
    page.updateDraft('selling_price', '42.50');
    page.updateDraft('purchase_price', '35.00');
    page.createProduct();
    expect(api.post).toHaveBeenCalledWith('products', {
      sku: 'MILK-1', barcode: null, name: 'Milk', description: '',
      unit: 'each', hsn_code: '0401', gst_rate: '5.00',
      selling_price: '42.50', purchase_price: '35.00', is_active: true,
    });
    expect(page.formOpen()).toBe(false);
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it('keeps the form open and shows server validation errors', () => {
    api.post.mockReturnValue(throwError(() => new ApiError('VALIDATION_ERROR', 'Please correct the fields.', { sku: ['This SKU already exists in the store.'] }, null, 400)));
    fixture.detectChanges();
    const page = fixture.componentInstance;
    page.openCreateForm();
    page.updateDraft('sku', 'milk-1');
    page.updateDraft('name', 'Milk');
    page.updateDraft('gst_rate', '5');
    page.updateDraft('selling_price', '42.50');
    page.updateDraft('purchase_price', '35.00');
    page.createProduct();
    fixture.detectChanges();
    expect(page.formOpen()).toBe(true);
    expect(page.fieldError('sku')).toContain('already exists');
    expect(fixture.nativeElement.textContent).toContain('Please correct the fields.');
  });

  it('does not accept invalid HSN, GST or price values', () => {
    fixture.detectChanges();
    const page = fixture.componentInstance;
    page.openCreateForm();
    page.updateDraft('sku', 'A-1');
    page.updateDraft('name', 'Item');
    page.updateDraft('hsn_code', '12345');
    page.updateDraft('gst_rate', '105');
    page.updateDraft('selling_price', '-1');
    page.updateDraft('purchase_price', '1.00');
    expect(page.canCreate()).toBe(false);
  });

  it('shows a retryable error when the list API request fails', () => {
    api.get.mockReturnValue(throwError(() => new Error('network')));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('We could not load products');
    expect(fixture.nativeElement.textContent).toContain('Try again');
  });
});
