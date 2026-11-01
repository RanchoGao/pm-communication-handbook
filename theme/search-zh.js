// mdBook's default English word index does not match Chinese substrings.
// Reuse its indexed documents, navigation and result UI for Chinese queries.
(() => {
  const original = elasticlunr.Index.prototype.search;
  elasticlunr.Index.prototype.search = function (query, options) {
    if (!/[\u3400-\u9fff]/u.test(query)) return original.call(this, query, options);
    const terms = query.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
    if (!terms.length) return [];
    return Object.entries(this.documentStore.docs).flatMap(([ref, doc]) => {
      const title = (doc.title || '').toLocaleLowerCase();
      const body = (doc.body || '').toLocaleLowerCase();
      if (!terms.every(term => (title + '\n' + body).includes(term))) return [];
      const score = terms.reduce((sum, term) => sum + (title.includes(term) ? 10 : 1), 0);
      return [{ ref, doc, score }];
    }).sort((a, b) => b.score - a.score);
  };
})();
