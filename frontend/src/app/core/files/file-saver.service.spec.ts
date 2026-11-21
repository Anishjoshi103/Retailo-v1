import { TestBed } from '@angular/core/testing';
import { FileSaver } from './file-saver.service';

describe('FileSaver', () => {
  it('saves a blob under the given name through the browser download', () => {
    Object.assign(URL, { createObjectURL: vi.fn().mockReturnValue('blob:x'), revokeObjectURL: vi.fn() });
    const names: string[] = [];
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    TestBed.inject(FileSaver).save(new Blob(['x']), 'file.csv');
    expect(names).toEqual(['file.csv']);
    click.mockRestore();
  });
});
