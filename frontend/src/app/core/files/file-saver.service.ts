import { Injectable } from '@angular/core';
import { saveBlob } from './save-blob';

/** Saves a downloaded file for the person. A service so screens can be tested without touching the browser. */
@Injectable({ providedIn: 'root' })
export class FileSaver {
  save(blob: Blob, filename: string): void {
    saveBlob(blob, filename);
  }
}
