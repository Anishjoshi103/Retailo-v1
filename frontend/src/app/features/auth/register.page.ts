import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { APP_CONFIG } from '../../core/config/app-config.token';

@Component({ selector:'retailo-register-page', standalone:true, imports:[ReactiveFormsModule,RouterLink], templateUrl:'./register.page.html', styleUrl:'./auth-form.page.scss', changeDetection:ChangeDetectionStrategy.OnPush })
export class RegisterPage {
  private readonly fb=inject(FormBuilder); private readonly http=inject(HttpClient); private readonly config=inject(APP_CONFIG);
  readonly submitting=signal(false); readonly errorMessage=signal(''); readonly successMessage=signal('');
  readonly form=this.fb.nonNullable.group({storeName:['',[Validators.required,Validators.maxLength(120)]],email:['',[Validators.required,Validators.email]],password:['',[Validators.required,Validators.minLength(12)]],confirmPassword:['',[Validators.required]]});
  submit():void { if(this.form.invalid){this.form.markAllAsTouched();return;} if(this.form.controls.password.value!==this.form.controls.confirmPassword.value){this.form.controls.confirmPassword.setErrors({mismatch:true});this.form.controls.confirmPassword.markAsTouched();return;}
    this.submitting.set(true);this.errorMessage.set('');this.successMessage.set('');
    this.http.post(this.config.apiBaseUrl.replace(/\/$/,'')+'/auth/register',{store_name:this.form.controls.storeName.value,email:this.form.controls.email.value,password:this.form.controls.password.value},{withCredentials:true}).subscribe({
      next:()=>{this.successMessage.set('Your registration request was received. Check your email for next steps.');this.form.reset();},
      error:(error:unknown)=>{this.errorMessage.set(error instanceof HttpErrorResponse&&error.status===0?'Unable to reach Retailo. Check your connection and try again.':'We could not complete registration. Check your details or contact your administrator.');},
    }).add(()=>this.submitting.set(false));
  }
}
