import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { APP_CONFIG } from '../../core/config/app-config.token';
import { SessionService } from '../../core/auth/session.service';
import { ApiError } from '../../core/api/api-error.model';
import { SessionContextService } from '../../core/auth/session-context.service';

interface LoginResponse { readonly access: string; }
@Component({ selector:'retailo-login-page', standalone:true, imports:[ReactiveFormsModule,RouterLink], templateUrl:'./login.page.html', styleUrl:'./login.page.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class LoginPage {
  private readonly fb=inject(FormBuilder);
  private readonly http=inject(HttpClient);
  private readonly config=inject(APP_CONFIG);
  private readonly session=inject(SessionService);
  private readonly sessionContext=inject(SessionContextService);
  private readonly router=inject(Router);
  private readonly route=inject(ActivatedRoute);
  readonly submitting=signal(false);
  readonly errorMessage=signal('');
  readonly form=this.fb.nonNullable.group({ email:['',[Validators.required,Validators.email]], password:['',[Validators.required,Validators.minLength(12)]] });
  submit():void {
    if(this.form.invalid){this.form.markAllAsTouched();return;}
    this.submitting.set(true);this.errorMessage.set('');
    const base=this.config.apiBaseUrl.replace(/\/$/,'');
    this.http.post<LoginResponse>(base+'/auth/login',this.form.getRawValue(),{withCredentials:true}).subscribe({
      next:(response)=>{if(!response.access){this.errorMessage.set('The server returned an invalid sign-in response.');this.submitting.set(false);return;}this.session.setAccessToken(response.access);this.sessionContext.load().subscribe((loaded)=>{if(loaded)this.sessionContext.loadBranches().subscribe();});const candidate=this.route.snapshot.queryParamMap.get('returnUrl');const returnUrl=candidate?.startsWith('/')&&!candidate.startsWith('//')?candidate:'/';void this.router.navigateByUrl(returnUrl);this.submitting.set(false);},
      error:(error:unknown)=>{this.errorMessage.set(this.messageFor(error));this.submitting.set(false);}
    });
  }
  private messageFor(error:unknown):string {
    if(error instanceof ApiError){if(error.status===0)return 'Unable to reach Retailo. Check your connection and try again.';if(error.status===401||error.code==='invalid_credentials')return 'Email or password is incorrect.';if(error.status===403||error.code==='no_active_store')return 'Your account does not have an active store. Contact your store owner.';if(error.status===400)return error.message;if(error.status>=500)return 'Retailo is temporarily unavailable. Try again shortly.';}
    return 'Sign-in failed. Please try again.';
  }
}
