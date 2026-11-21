import { saveBlob } from './save-blob';

describe('saveBlob', () => {
  it('downloads the file under the given name and releases the object URL', () => {
    const createUrl = vi.fn().mockReturnValue('blob:fake');
    const revokeUrl = vi.fn();
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: revokeUrl });
    const clicked: { href: string; download: string }[] = [];
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push({ href: this.href, download: this.download });
    });
    const blob = new Blob(['a,b'], { type: 'text/csv' });
    saveBlob(blob, 'gst-rates.csv');
    expect(createUrl).toHaveBeenCalledWith(blob);
    expect(clicked).toEqual([{ href: 'blob:fake', download: 'gst-rates.csv' }]);
    expect(revokeUrl).toHaveBeenCalledWith('blob:fake');
    expect(document.querySelector('a[download]')).toBeNull();
    click.mockRestore();
  });
});
