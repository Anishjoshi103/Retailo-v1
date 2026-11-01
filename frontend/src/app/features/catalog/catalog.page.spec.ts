import { provideHttpClient } from '@angular/common/http';
import { HttpParams } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ApiClient } from '../../core/api/api-client.service';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { CatalogPage } from './catalog.page';

describe('CatalogPage', () => {
  let fixture: ComponentFixture<CatalogPage>;
  let api: { get: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    api = { get: vi.fn().mockReturnValue(of([])) };
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

  it('shows a retryable error when the API request fails', () => {
    api.get.mockReturnValue(throwError(() => new Error('network')));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('We could not load products');
    expect(fixture.nativeElement.textContent).toContain('Try again');
  });
});
