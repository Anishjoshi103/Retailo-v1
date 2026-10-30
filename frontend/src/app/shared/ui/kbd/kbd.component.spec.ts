import { TestBed } from '@angular/core/testing'; import { KbdComponent } from './kbd.component';
describe('KbdComponent',()=>{it('creates',async()=>{await TestBed.configureTestingModule({imports:[KbdComponent]}).compileComponents();expect(TestBed.createComponent(KbdComponent).componentInstance).toBeTruthy();});});
