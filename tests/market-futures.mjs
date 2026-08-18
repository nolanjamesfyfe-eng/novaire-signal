import assert from 'node:assert/strict';
import { buildExchangeQuote, parseInvestingFutures, parseYahooChart } from '../api/market-futures.js';

const payload = {
  chart: {
    result: [{
      meta: { regularMarketTime: 1786739967 },
      timestamp: [1786455000, 1786541400, 1786627800, 1786714200],
      indicators: { quote: [{ close: [23250, null, 23400, 23517] }] },
    }],
    error: null,
  },
};

const quote = parseYahooChart(payload);
assert.equal(quote.price, 23517);
assert.equal(quote.previous, 23400);
assert.equal(quote.change, 0.5);
assert.equal(quote.source, 'Yahoo Finance');
assert.equal(quote.period, 'futures session');
assert.equal(quote.quoteTime, '2026-08-14T20:39:27.000Z');

const investingMarkdown = `
| | Name | Month | Last | High | Low | Chg. | Chg. % | Time |
| | [**US 30**](https://www.investing.com/indices/us-30-futures?cid=1175152 "US 30 - (CFD)") derived | | 53,467.60 | 53,485.60 | 53,427.70 | +7.60 | +0.01% | 20:29:46 |
| | [**US 500**](https://www.investing.com/indices/us-spx-500-futures?cid=1175153 "US 500 - (CFD)") derived | | 7,748.60 | 7,750.40 | 7,742.70 | +3.20 | +0.04% | 20:29:11 |
| | [**US Tech 100**](https://www.investing.com/indices/nq-100-futures?cid=1175151 "US Tech 100 - (CFD)") derived | | 30,012.20 | 30,024.60 | 29,974.30 | +16.80 | +0.06% | 20:29:53 |
### US Futures Market Quotes (10-minute Delayed)
| | Name | Month | Last | High | Low | Chg. | Chg. % | Time |
| | [**Dow Jones**](https://www.investing.com/indices/us-30-futures "Dow Jones") | Sep 26 | 53,541.00 | 53,544.00 | 53,519.00 | -3.00 | -0.01% | 20:19:50 |
| | [**S&P 500**](https://www.investing.com/indices/us-spx-500-futures "S&P 500") | Sep 26 | 7,770.25 | 7,770.50 | 7,767.00 | +1.50 | +0.02% | 20:20:05 |
| | [**Nasdaq 100**](https://www.investing.com/indices/nq-100-futures "Nasdaq 100") | Sep 26 | 30,109.25 | 30,109.50 | 30,086.00 | +13.25 | +0.04% | 20:19:49 |
`;
const investing = parseInvestingFutures(investingMarkdown);
assert.equal(investing['ES=F'].exchange.price, 7770.25);
assert.equal(investing['ES=F'].derived.change, 0.04);
assert.equal(investing['NQ=F'].exchange.change, 0.04);
assert.equal(investing['YM=F'].derived.price, 53467.6);

const exchangeQuote = buildExchangeQuote(
  {symbol:'ES=F', price:7747.25, change:-0.74, source:'Yahoo Finance'},
  investing['ES=F'],
);
assert.equal(exchangeQuote.price, 7747.25, 'Yahoo front-month exchange future is primary');
assert.equal(exchangeQuote.change, -0.74, 'the displayed move remains the primary exchange quote move');
assert.equal(exchangeQuote.source, 'Yahoo Finance · CME/CBOT front month');
assert.equal(exchangeQuote.isFallback, false);
const fallback = buildExchangeQuote({symbol:'ES=F', price:null, change:null}, investing['ES=F']);
assert.equal(fallback.price, 7770.25, 'Investing exchange future is the fallback');
assert.equal(fallback.change, 0.02);
assert.equal(fallback.isFallback, true);
console.log('market futures parser and canonical exchange quote: ok');
