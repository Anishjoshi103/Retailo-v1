import { ChangeDetectionStrategy, Component, signal } from '@angular/core';

@Component({
  selector: 'retailo-home-page',
  standalone: true,
  template: `
    <main class="shell">
      <header class="topbar">
        <a class="brand" href="/" aria-label="Retailo home">
          <span class="brand-mark" aria-hidden="true">R</span>
          <span>Retailo</span>
        </a>
        <span class="environment">Development workspace</span>
      </header>

      <section class="hero" aria-labelledby="page-title">
        <p class="eyebrow">RETAIL OPERATIONS, SIMPLIFIED</p>
        <h1 id="page-title">A clearer view of your store.</h1>
        <p class="intro">Your retail workspace foundation is ready. Sales, inventory and GST workflows will appear here as the platform is built.</p>
        <div class="status" role="status">
          <span class="status-dot" aria-hidden="true"></span>
          <span>{{ statusMessage() }}</span>
        </div>
      </section>

      <section class="modules" aria-label="Planned modules">
        @for (module of modules; track module.name) {
          <article class="module-card">
            <span class="module-number">{{ module.number }}</span>
            <h2>{{ module.name }}</h2>
            <p>{{ module.description }}</p>
            <span class="module-state">Planned</span>
          </article>
        }
      </section>

      <footer>Retailo · Built for Indian retail teams</footer>
    </main>
  `,
  styles: [`
    :host { display: block; min-height: 100vh; }
    .shell { max-width: 1120px; margin: 0 auto; padding: 0 28px; }
    .topbar { height: 84px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e1e6ef; }
    .brand { display: inline-flex; align-items: center; gap: 10px; color: #172554; font-size: 21px; font-weight: 750; text-decoration: none; letter-spacing: -0.04em; }
    .brand-mark { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; color: white; background: #1d4ed8; }
    .environment { color: #64748b; font-size: 13px; }
    .hero { padding: 76px 0 54px; max-width: 690px; }
    .eyebrow { color: #1d4ed8; font-size: 12px; font-weight: 800; letter-spacing: .13em; }
    h1 { margin: 18px 0; color: #172554; font-size: clamp(36px, 6vw, 58px); line-height: 1.04; letter-spacing: -.055em; }
    .intro { max-width: 600px; color: #536178; font-size: 17px; line-height: 1.7; }
    .status { display: inline-flex; align-items: center; gap: 10px; margin-top: 18px; padding: 10px 14px; border: 1px solid #dbeafe; border-radius: 999px; background: #eff6ff; color: #1e40af; font-size: 13px; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #2563eb; }
    .modules { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
    .module-card { min-height: 185px; padding: 22px; border: 1px solid #e1e6ef; border-radius: 16px; background: white; box-shadow: 0 5px 20px #17255408; }
    .module-number { color: #2563eb; font-size: 12px; font-weight: 800; }
    h2 { margin: 20px 0 8px; color: #172554; font-size: 18px; }
    .module-card p { min-height: 42px; margin: 0 0 16px; color: #64748b; font-size: 14px; line-height: 1.5; }
    .module-state { color: #64748b; font-size: 12px; font-weight: 700; }
    footer { padding: 46px 0 28px; color: #8490a3; font-size: 12px; }
    @media (max-width: 720px) { .shell { padding: 0 18px; } .hero { padding: 54px 0 38px; } .modules { grid-template-columns: 1fr; } .module-card { min-height: auto; } .environment { font-size: 11px; } }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class HomePage {
  readonly statusMessage = signal('Application shell loaded');
  readonly modules = [
    { number: '01', name: 'Point of sale', description: 'A fast, cashier-friendly checkout flow.' },
    { number: '02', name: 'Inventory', description: 'Stock levels, movements and adjustments.' },
    { number: '03', name: 'GST & reports', description: 'Tax-ready records and business insights.' }
  ];
}
