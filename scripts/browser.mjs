// Shared browser engine for diagrams, covers, PDF and website verification.
import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [mode, input, output] = process.argv.slice(2);
const executablePath = process.env.BOOK_CHROME;
const browser = await chromium.launch({ ...(executablePath ? { executablePath } : {}), headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1000, height: 1400 }, deviceScaleFactor: 2 });
  if (mode === 'diagram') {
    await page.setContent('<html lang="zh-CN"><head><meta charset="utf-8"></head><body style="margin:24px;background:white"><div id="diagram"></div></body></html>');
    await page.addScriptTag({ path: path.resolve('node_modules/mermaid/dist/mermaid.min.js') });
    const definition = await fs.readFile(input, 'utf8');
    await page.evaluate(async definition => {
      mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: 'neutral', fontFamily: 'sans-serif'});
      const {svg} = await mermaid.render('book-diagram', definition);
      document.querySelector('#diagram').innerHTML = svg;
    }, definition);
    await page.evaluate(() => document.fonts.ready);
    await page.locator('#diagram svg').screenshot({ path: output });
  } else if (mode === 'cover') {
    await page.setViewportSize({ width: 1000, height: 1400 });
    await page.setContent(`<html lang="zh-CN"><meta charset="utf-8"><body style="margin:0;background:#102e39;color:#f3f5ef;font-family:sans-serif"><main style="box-sizing:border-box;padding:110px 85px;height:1400px;border-top:24px solid #40c7af"><p style="color:#61d7bf;font-size:24px;letter-spacing:5px">PRODUCT COMMUNICATION</p><h1 style="font-size:84px;line-height:1.4;margin-top:120px">产品经理<br>沟通手册</h1><p style="font-size:32px;color:#c7d7da;line-height:1.8">先判断处境<br>再选择行动</p><p style="margin-top:180px;font-size:28px">EurekaGao</p></main></body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: output });
  } else if (mode === 'pdf') {
    await page.goto(pathToFileURL(path.resolve(input)).href);
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.locator('table, pre').evaluateAll(nodes => nodes.filter(n => n.scrollWidth > n.clientWidth + 2).length);
    if (overflow) throw new Error(`Print content overflows: ${overflow}`);
    await page.pdf({ path: output, format: 'A5', preferCSSPageSize: true, printBackground: true,
      displayHeaderFooter: true, outline: true, tagged: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="width:100%;text-align:center;font-size:8px;color:#607580"><span class="pageNumber"></span></div>' });
  } else if (mode === 'check-site') {
    const address = input;
    await page.goto(address);
    await page.locator('#mdbook-sidebar-toggle').waitFor();
    await page.locator('.download-panel a').first().waitFor();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(new URL('00_阅读指南_V1_2026-11-01.html', address).href);
    await page.locator('.mermaid svg').waitFor();
    await page.locator('#mdbook-search-toggle').click();
    await page.locator('#mdbook-searchbar').fill('延期');
    await page.locator('#mdbook-searchbar').press('ArrowRight');
    await page.waitForFunction(() => document.querySelectorAll('#mdbook-searchresults a').length > 0, null, { timeout: 15000 });
    if (!(await page.locator('#mdbook-searchresults').textContent()).includes('延期')) throw new Error('Chinese query has unrelated results');
    await page.screenshot({ path: path.join(output, 'website-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(address);
    await page.screenshot({ path: path.join(output, 'website-mobile.png'), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    if (overflow) throw new Error('Mobile page overflows horizontally');
    await page.locator('main').getByRole('link', { name: '目录', exact: true }).click();
    await page.waitForURL(/SUMMARY\.html/);
    await page.locator('main h1').filter({ hasText: '章节目录' }).waitFor();
    await page.locator('#mdbook-sidebar-toggle').click();
    await page.locator('#mdbook-sidebar').getByRole('link', { name: '3. 说明白', exact: true }).click();
    await page.waitForURL(/03_/);
    await page.locator('main h1').filter({ hasText: '说明白' }).waitFor();
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('Site: directory, Mermaid, Chinese search and mobile page passed');
  } else {
    throw new Error(`Unknown browser mode: ${mode}`);
  }
} finally { await browser.close(); }
