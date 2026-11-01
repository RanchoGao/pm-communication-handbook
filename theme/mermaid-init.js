(() => {
  const run = () => {
    document.querySelectorAll('pre code.language-mermaid').forEach(code => {
      const div = document.createElement('div');
      div.className = 'mermaid';
      div.textContent = code.textContent;
      code.parentElement.replaceWith(div);
    });
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral',
      fontFamily: '"Noto Sans CJK SC", "Microsoft YaHei", sans-serif' });
    mermaid.run({ querySelector: '.mermaid' });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
