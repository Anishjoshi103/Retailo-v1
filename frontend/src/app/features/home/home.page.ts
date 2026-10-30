import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { APP_ENVIRONMENT } from '../../core/config/app-environment.token';
import { PLANNED_MODULES } from './home.data';

@Component({
  selector: 'retailo-home-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './home.page.html',
  styleUrl: './home.page.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class HomePage {
  private readonly appEnvironment = inject(APP_ENVIRONMENT);

  readonly statusMessage = signal('Application shell loaded');
  readonly modules = PLANNED_MODULES;
  readonly showEnvironmentLabel = this.appEnvironment.showEnvironmentLabel;
  readonly environmentLabel = this.appEnvironment.environmentLabel;
}
