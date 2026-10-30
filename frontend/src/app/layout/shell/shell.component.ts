import { ChangeDetectionStrategy, Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { SidenavComponent } from '../sidenav/sidenav.component';
import { TopbarComponent } from '../topbar/topbar.component';
@Component({ selector: 'retailo-shell', standalone: true, imports: [RouterOutlet, TopbarComponent, SidenavComponent], templateUrl: './shell.component.html', styleUrl: './shell.component.scss', changeDetection: ChangeDetectionStrategy.OnPush })
export class ShellComponent {
  readonly drawerOpen = signal(false);
  toggleDrawer(): void { this.drawerOpen.update((value) => !value); }
  closeDrawer(): void { this.drawerOpen.set(false); }
}