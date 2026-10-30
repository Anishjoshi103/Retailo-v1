import { describe, expect, it } from 'vitest';
import { LoadingService } from './loading.service';
describe('LoadingService', () => { it('tracks concurrent requests without going negative', () => { const service=new LoadingService(); service.begin(); service.begin(); expect(service.isLoading()).toBe(2); service.end(); service.end(); service.end(); expect(service.isLoading()).toBe(0); }); });