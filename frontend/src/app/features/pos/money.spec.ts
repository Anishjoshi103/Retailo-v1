import { formatMoney, formatQuantity, formatRupees, lineGross, parseMoney, parseQuantity, priceCart } from './money';

describe('money helpers', () => {
  it('parses decimal strings exactly into paise', () => {
    expect(parseMoney('100')).toBe(10000);
    expect(parseMoney('42.5')).toBe(4250);
    expect(parseMoney('33.33')).toBe(3333);
    expect(parseMoney(' 0.05 ')).toBe(5);
  });

  it('rejects malformed, negative and over-precise amounts', () => {
    for (const bad of ['', 'abc', '-1', '1.234', '1,5', '1e3', '.5', '5.']) {
      expect(parseMoney(bad), bad).toBeNull();
    }
  });

  it('parses quantities to milli-units and rejects zero or over-precise values', () => {
    expect(parseQuantity('2')).toBe(2000);
    expect(parseQuantity('0.333')).toBe(333);
    expect(parseQuantity('1.5')).toBe(1500);
    for (const bad of ['0', '0.000', '-1', '1.2345', 'x', '']) {
      expect(parseQuantity(bad), bad).toBeNull();
    }
  });

  it('formats paise and milli-units', () => {
    expect(formatMoney(10040)).toBe('100.40');
    expect(formatMoney(5)).toBe('0.05');
    expect(formatMoney(-40)).toBe('-0.40');
    expect(formatMoney(0)).toBe('0.00');
    expect(formatQuantity(2000)).toBe('2.000');
    expect(formatQuantity(333)).toBe('0.333');
  });

  it('formats rupees with the sign in front', () => {
    expect(formatRupees(10040)).toBe('₹100.40');
    expect(formatRupees(0)).toBe('₹0.00');
    expect(formatRupees(-40)).toBe('-₹0.40');
  });

  it('rounds a line gross half-up to paise', () => {
    expect(lineGross(10000, 2000)).toBe(20000);
    expect(lineGross(3333, 3000)).toBe(9999);
    expect(lineGross(4500, 333)).toBe(1499); // 14.985 -> 14.99
    expect(lineGross(1, 500)).toBe(1); // 0.005 -> 0.01
  });

  it('matches the server for the documented invoice examples', () => {
    expect(priceCart([{ pricePaise: 10000, quantityMilli: 2000 }])).toEqual({ exactPaise: 20000, grandTotalPaise: 20000, roundOffPaise: 0 });
    expect(priceCart([{ pricePaise: 3333, quantityMilli: 3000 }])).toEqual({ exactPaise: 9999, grandTotalPaise: 10000, roundOffPaise: 1 });
    expect(priceCart([{ pricePaise: 1040, quantityMilli: 1000 }])).toEqual({ exactPaise: 1040, grandTotalPaise: 1000, roundOffPaise: -40 });
    expect(priceCart([
      { pricePaise: 10000, quantityMilli: 2000 },
      { pricePaise: 3333, quantityMilli: 3000 },
    ])).toEqual({ exactPaise: 29999, grandTotalPaise: 30000, roundOffPaise: 1 });
  });

  it('rounds exactly half a rupee up', () => {
    expect(priceCart([{ pricePaise: 1050, quantityMilli: 1000 }]).grandTotalPaise).toBe(1100);
    expect(priceCart([{ pricePaise: 1049, quantityMilli: 1000 }]).grandTotalPaise).toBe(1000);
  });

  it('prices an empty cart as zero', () => {
    expect(priceCart([])).toEqual({ exactPaise: 0, grandTotalPaise: 0, roundOffPaise: 0 });
  });
});
