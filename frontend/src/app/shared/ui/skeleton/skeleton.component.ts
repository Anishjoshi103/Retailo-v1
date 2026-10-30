import { ChangeDetectionStrategy, Component, input } from '@angular/core';
@Component({selector:'rt-skeleton',standalone:true,templateUrl:'./skeleton.component.html',styleUrl:'./skeleton.component.scss',changeDetection:ChangeDetectionStrategy.OnPush})
export class SkeletonComponent { width=input('100%'); height=input('1rem'); }
