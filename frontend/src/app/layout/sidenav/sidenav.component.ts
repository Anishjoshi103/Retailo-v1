import { ChangeDetectionStrategy, Component, EventEmitter, inject, Input, Output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { RouteRoleContext } from '../../core/auth/role-branch.guard';
import { NavigationItem } from '../../shared/models/navigation-item.model';
@Component({ selector:'retailo-sidenav', standalone:true, imports:[RouterLink,RouterLinkActive], templateUrl:'./sidenav.component.html', styleUrl:'./sidenav.component.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class SidenavComponent {
  @Input() drawerOpen = false; @Output() readonly navigate = new EventEmitter<void>();
  private readonly access = inject(RouteRoleContext);
  readonly items: readonly NavigationItem[] = [
    {label:'Dashboard',route:'/',icon:'⌂'},{label:'Point of sale',route:'/pos',icon:'▣'},{label:'Catalog',route:'/catalog',icon:'▤'},
    {label:'Inventory',route:'/inventory',icon:'▥'},{label:'GST & invoices',route:'/gst',icon:'₹'},
    {label:'Reports',route:'/reports',icon:'▥',roles:['owner','admin','manager']},{label:'Settings',route:'/settings',icon:'⚙',roles:['owner','admin']}
  ];
  visibleItems(): readonly NavigationItem[] { const roles=this.access.roles(); return this.items.filter((item)=>!item.roles||item.roles.some((role)=>roles.includes(role))); }
}