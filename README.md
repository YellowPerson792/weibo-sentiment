# Weibo Sentiment Explorer

一个基于 Streamlit 的微博热帖评论情绪分析平台，支持爬取真实评论、调用中文情绪模型进行六维度多标签推理，并以图表形式呈现结果。

---

## ✨ 功能亮点

- **URL 一键分析**：输入微博热帖链接即可自动完成评论抓取、情绪分析和结果展示。
- **多入口输入**：除 URL 外，还支持单条文本实时分析和文件批量导入（CSV/XLSX/TXT）。
- **可视化与历史记录**：表格、饼图、词云等视图直观呈现情绪分布，SQLite 保存结果方便回溯。
- **高质量模型**：接入 Hugging Face 中文零样本模型 `IDEA-CCNL/Erlangshen-RoBERTa-330M-NLI`，并提供关键词回退策略保证离线可用。

---

## 🧱 目录结构

```
.
├── README.md
├── MODULES.md                # 模块详解及改进建议
├── Requirement.md            # 初始需求
└── weibo_sentiment
    ├── app.py                # Streamlit 入口
    ├── crawler.py            # 微博爬虫
    ├── sentiment.py          # 情绪推理封装
    ├── db.py                 # SQLite 持久层
    ├── utils.py              # 词云/饼图工具
    ├── requirements.txt
    └── models/               # 可选：HF 模型缓存目录
```

各模块之间的详细关系可参考 `MODULES.md`。

---

## 🚀 快速开始

### 1. 环境准备

```bash
git clone https://github.com/YellowPerson792/weibo-sentiment.git
cd weibo_sentiment
pip install -r requirements.txt
```

> 推荐设置 Hugging Face 镜像以加速模型下载：
> ```bash
> set HF_ENDPOINT=https://hf-mirror.com          # Windows CMD
> export HF_ENDPOINT=https://hf-mirror.com       # macOS / Linux
> ```
> 可选：设置 `HF_HOME` 指向 `weibo_sentiment/models` 以便离线缓存。

### 2. 启动服务

```bash
streamlit run weibo_sentiment/app.py
```

浏览器访问 `http://127.0.0.1:8501` 即可进入系统。

---

## 🔧 关键技术

| 模块         | 说明                                                                                           |
| ------------ | ---------------------------------------------------------------------------------------------- |
| `crawler.py` | 采用 `requests`+`BeautifulSoup`，模拟移动端 visitor 流程，调用 `m.weibo.cn` 接口抓取评论和元信息。 |
| `sentiment.py` | 调用 Hugging Face zero-shot pipeline，对评论文本打分并输出六情绪标签，支持关键词启发式回退。   |
| `db.py`      | 维护 `posts`、`comments`、`emotions` 表，提供插入与查询 API，供前端读取历史数据和分布。        |
| `utils.py`   | 承载饼图、词云等可视化辅助方法，以及中文分词工具。                                             |
| `app.py`     | 调度上述模块，提供 URL 分析 / 文本分析 / 文件导入 / 历史查询等页面。                            |

---

## 📊 使用流程

1. **网址直分析**  
   输入微博链接 → 选择抓取评论数 → 点击“开始采集并分析” → 等待分析结果 → 查看表格、情绪饼图、词云。

2. **文本即时分析**  
   粘贴任意中文评论 → 配置情绪阈值 → 点击“分析文本” → 获取概率与标签。

3. **文件批量分析**  
   上传 CSV/XLSX/TXT（需包含 `text` 字段） → 一键分析 → 查看结果表。

4. **历史查询**  
   在下拉框选择之前分析过的热帖 → 回放当时的数据与图表。

---

## 🧩 后续扩展

- 增设评论分页与筛选、情绪阈值自定义、导出数据等高级功能。
- 引入代理、异步抓取和更完善的错误提示，提升采集稳定性。
- 加入 Dockerfile、CI 流水线与更丰富的测试覆盖，便于部署。

如需更详细的模块描述和改进建议，请参阅 `MODULES.md`。欢迎 Issue / PR 交流反馈！ ❤️

