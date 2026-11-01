import { HttpClient, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';
import { APP_CONFIG } from '../config/app-config.token';
import { ApiClient } from './api-client.service';

describe('ApiClient URL construction', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('prefixes the configured API base exactly once', () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } },
      ],
    });
    TestBed.inject(ApiClient).get('products').subscribe();
    const request = TestBed.inject(HttpTestingController).expectOne('/api/v1/products');
    request.flush([]);
  });
});
