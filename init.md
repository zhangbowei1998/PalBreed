# 幻兽帕鲁配种 Agent — 初始需求

> 📖 历史原始需求草稿。完整文档在 `docs/` 目录下，AI 接手请先阅读 `docs/context/CONTEXT.md`（导航见 `docs/README.md`）

---

我要做一个幻兽帕鲁配种的agent。输入想要的帕鲁，给我一个配种方案。
目前已知的需求是：
1. 输入方式可以打字或者语音
2. 用户可能想要的是某一个工作种类等级为多少的帕鲁。比如手工10级的帕鲁，但是用户不知道具体是哪个帕鲁，返回给用户的结果应该是具体符合要求的帕鲁和配种方案
3. 返回的配种方案要从最基础的帕鲁开始返回一个配种树。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [`docs/context/CONTEXT.md`](./docs/context/CONTEXT.md) | 🔰 AI 接手快速上下文 |
| [`docs/README.md`](./docs/README.md) | 📖 文档总索引（分类导航） |
| [`docs/architecture/design/PROJECT_STRUCTURE.md`](./docs/architecture/design/PROJECT_STRUCTURE.md) | 📁 目录结构与依赖关系 |
| [`.github/copilot-instructions.md`](./.github/copilot-instructions.md) | 🤖 AI 行为规范 |