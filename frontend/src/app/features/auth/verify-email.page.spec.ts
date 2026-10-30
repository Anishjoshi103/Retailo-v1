import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { VerifyEmailPage } from './verify-email.page';

describe('VerifyEmailPage', () => {
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VerifyEmailPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
        { provide: APP_CONFIG, useValue: { apiBaseUrl: '/api/v1' } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: { get: (key: string) => key === 'token' ? 'signed-token' : null } } } }],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  it('posts the verification token and shows the API success message', () => {
    const fixture = TestBed.createComponent(VerifyEmailPage);
    fixture.detectChanges();
    const request = http.expectOne('/api/v1/auth/verify-email');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ token: 'signed-token' });
    request.flush({ detail: 'Email verified. You can now sign in.' });
    fixture.detectChanges();
    expect(fixture.componentInstance.success()).toBe(true);
    expect(fixture.nativeElement.textContent).toContain('Email verified. You can now sign in.');
  });
});
