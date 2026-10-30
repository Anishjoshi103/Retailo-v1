import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';
import { APP_ENVIRONMENT } from '../../core/config/app-environment.token';
import { environment } from '../../../environments/environment';
import { productionEnvironment } from '../../../environments/environment.prod';
import { HomePage } from './home.page';

describe('HomePage', () => {
  async function createComponent(appEnvironment = environment) {
    await TestBed.configureTestingModule({
      imports: [HomePage],
      providers: [
        provideRouter([]),
        { provide: APP_ENVIRONMENT, useValue: appEnvironment }
      ]
    }).compileComponents();

    const fixture = TestBed.createComponent(HomePage);
    fixture.detectChanges();
    return fixture;
  }

  it('renders the page title', async () => {
    const fixture = await createComponent();
    expect(fixture.nativeElement.querySelector('h1')?.textContent).toContain(
      'A clearer view of your store.'
    );
  });

  it('renders exactly three planned module cards', async () => {
    const fixture = await createComponent();
    expect(fixture.nativeElement.querySelectorAll('.module-card').length).toBe(3);
  });

  it('hides the environment label in production', async () => {
    const fixture = await createComponent(productionEnvironment);
    expect(fixture.nativeElement.querySelector('.environment')).toBeNull();
  });
});
