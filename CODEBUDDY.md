# 产品经理沟通手册 — 项目约定

CodeBuddy 项目记忆。只写高频硬约束和入口，详细规则以仓库内文档为准。

## 项目是什么

面向产品经理的场景化沟通手册，用 mdBook 做分章电子书，一次源文件产出网站、EPUB、PDF 三种格式。

- 正文只维护 `book/` 一套，不要另建副本。
- 阅读顺序只由 `book/SUMMARY.md` 决定；根目录 `SUMMARY.md` 是面向 GitHub 的镜像，两者必须同步。
- 当前进度与待办见 `项目进度_V5_2026-11-01.md`。

## 常用命令

```shell
npm ci --ignore-scripts            # 首次安装
python scripts/setup_tools.py      # mdBook / Pandoc 等装到 .tools/
npx playwright install chromium

python scripts/build.py check      # 章节、锚点、内部链接检查，改完必跑
python scripts/build.py all --version V1 --date 2026-11-01
python scripts/check_site.py       # 网站链接检查 + Chromium 实测
python scripts/check_epub.py       # EPUBCheck 5.3.0（需 Java）
```

`site/`、`dist/`、`build/`、`.tools/`、`node_modules/` 都是产物，不提交。构建失败不要静默跳过。

## 改书稿时的硬约束

- 标题前的 `<a id="..."></a>` 不能删改；网站、EPUB、PDF 的跨章链接都依赖它。
- 新增、改名或升版本：同步 `book/SUMMARY.md`、根 `SUMMARY.md` 和正文里的跨章引用，然后跑 `build.py check`。
- 外部原稿不改；旧稿备份在 `.local-history/`，不发布。
- 真实案例匿名化，演绎案例明确标注。

## 写作规范

详见 `编辑规范_V3_2026-11-01.md`。要点：

- 简体中文、短句、具体动作；术语首次出现给一句大白话解释。
- 结构固定：判断处境 → 条件分岔 → 行动步骤 → 参考话术 → 适用边界。
- 公开内容署名 EurekaGao，不出现真实姓名、公司名、客户与内部敏感信息。
- 不写万能话术，不给无条件承诺。

## 文件命名

自定义文档用 `主题_V版本号_创建日期`（如 `构建与发布_V3_2026-11-01.md`）；README、SUMMARY、CONTRIBUTING、LICENSE、CODEBUDDY 用约定名。
同一对话内每修改一次自定义文档，版本号 +1，并同步所有引用它的链接（README、项目进度等）。

## 构建与发布

详见 `构建与发布_V3_2026-11-01.md`。远端仓库尚未连接，Pages 与 Release 都还没实际发布过。
