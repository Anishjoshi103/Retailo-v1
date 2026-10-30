import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { APP_CONFIG } from '../../core/config/app-config.token';

@Component({ selector:'retailo-password-recovery-page', standalone:true, imports:[ReactiveFormsModule,RouterLink], templateUrl:'./password-recovery.page.html', styleUrl:'./auth-form.page.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class PasswordRecoveryPage {
  private readonly fb=inject(FormBuilder); private readonly http=inject(HttpClient); private readonly config=inject(APP_CONFIG);
  readonly submitting=signal(false); readonly errorMessage=signal(''); readonly submitted=signal(false);
  readonly form=this.fb.nonNullable.group({email:['',[Validators.required,Validators.email]]});
  submit():void { if(this.form.invalid){this.form.markAllAsTouched();return;}this.submitting.set(true);this.errorMessage.set('');
    this.http.post(this.config.apiBaseUrl.replace(/\/$/,'')+'/auth/password-reset/request',{email:this.form.controls.email.value},{withCredentials:true}).subscribe({
      next:()=>this.submitted.set(true),
      error:(error:unknown)=>{if(error instanceof HttpErrorResponse&&error.status===0)this.errorMessage.set('Unable to reach Retailo. Check your connection and try again.');else this.submitted.set(true);},
    }).add(()=>this.submitting.set(false));
  }
}
