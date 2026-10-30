import { HttpClient, HttpContext, HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { APP_CONFIG } from '../config/app-config.token';
export interface ApiRequestOptions { readonly headers?: HttpHeaders; readonly params?: HttpParams; readonly context?: HttpContext; readonly withCredentials?: boolean; }
@Injectable({ providedIn: 'root' })
export class ApiClient {
  private readonly http = inject(HttpClient); private readonly config = inject(APP_CONFIG);
  get<T>(path: string, options: ApiRequestOptions = {}): Observable<T> { return this.http.get<T>(this.url(path), options); }
  post<R, B>(path: string, body: B, options: ApiRequestOptions = {}): Observable<R> { return this.http.post<R>(this.url(path), body, options); }
  put<R, B>(path: string, body: B, options: ApiRequestOptions = {}): Observable<R> { return this.http.put<R>(this.url(path), body, options); }
  delete<T>(path: string, options: ApiRequestOptions = {}): Observable<T> { return this.http.delete<T>(this.url(path), options); }
  private url(path: string): string { return `${this.config.apiBaseUrl.replace(/\/$/, '')}/${path.replace(/^\//, '')}`; }
}