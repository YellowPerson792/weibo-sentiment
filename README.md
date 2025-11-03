# 微博评论情绪分析与可视化系统

## 项目概述

本项目实现了一个端到端的微博热帖评论情绪分析平台。系统围绕以下核心能力构建：

- **自动采集热帖评论**：通过移动端公开接口 + 访客 Cookie 握手流程，支持输入微博 URL 后自动批量抓取评论、点赞数和时间戳等信息。
- **六情绪多标签判别**：使用 Hugging Face 模型 `IDEA-CCNL/Erlangshen-RoBERTa-330M-NLI` 进行零样本情绪分类，涵盖愤怒、厌恶、恐惧、喜悦、悲伤、惊讶六种情绪。若模型不可用，会回退到中文关键词启发式算法。
- **可视化与历史查询**：基于 Streamlit 以网页形式展现评论明细、饼图、词云以及历史分析记录，支持 URL 直分析、单条文本分析与文件批量导入。
- **数据持久化**：使用 SQLite 存储热帖元信息、评论与情绪结果，便于后续复用与复查。


## 目录结构

```
.
├── README.md                  # 项目说明文档（当前文件）
├── Requirement.md             # 初始需求文档
└── weibo_sentiment
    ├── app.py                 # Streamlit 入口
    ├── crawler.py             # 微博爬虫（移动端公开 API + visitor 握手）
    ├── sentiment.py           # 情绪推理封装（HF 模型 + 启发式兜底）
    ├── db.py                  # SQLite 持久层
    ├── utils.py               # 词云/饼图等可视化工具
    ├── requirements.txt       # 运行所需依赖
    └── models
        └── erlangshen-roberta-nli/  # 已下载的 HF 模型权重（可选）
```


## 快速开始

1. **安装依赖**

   ```bash
   pip install -r weibo_sentiment/requirements.txt
   ```

2. **准备模型**

   - 默认会自动从 Hugging Face 下载 `IDEA-CCNL/Erlangshen-RoBERTa-330M-NLI`。
   - 若需要离线运行，可先执行：

     ```bash
     hf-mirror download IDEA-CCNL/Erlangshen-RoBERTa-330M-NLI \
       --cache-dir weibo_sentiment/models
     ```

   - 运行前建议设置镜像加速路径：

     ```bash
     set HF_ENDPOINT=https://hf-mirror.com
     set HF_HOME=%CD%\weibo_sentiment\models   # 依操作系统调整
     ```

3. **启动服务**

   ```bash
   streamlit run weibo_sentiment/app.py
   ```

   网页默认监听 `http://127.0.0.1:8501`。


## 功能特性

- **URL 直达分析**：输入微博热帖链接，自动抓取评论 -> 调用情绪模型 -> 保存结果 -> 页面展示。
- **文本即时分析**：用于演示单条文本情绪预测，可调节标签阈值。
- **文件批量导入**：支持 CSV / XLSX / TXT 批量处理评论文本。
- **历史记录**：从 SQLite 查询已分析的帖子，再次展示当时的情绪分布与可视化图表。
- **数据增强**：
  - 评论在写库前做 HTML 解析与换行清理。
  - 词云使用 `jieba` 中文分词，支持停用词过滤的扩展（待实现）。
  - 饼图基于平均情绪概率计算，避免单条评论噪声。


## 关键技术

- **爬虫 `crawler.py`**
  - `WeiboClient` 负责 visitor cookie 的 `genvisitor` 与 `incarnate` 握手。
  - 调用 `https://m.weibo.cn/statuses/show` 获取帖子信息，并使用 `https://m.weibo.cn/comments/hotflow` 分页抓取评论。
  - 自动提取用户昵称、评论正文、时间戳、点赞数。

- **情绪推理 `sentiment.py`**
  - 通过 `transformers.pipeline("zero-shot-classification")` 实现多标签分类。
  - 中文情绪标签与模型输出采用 softmax 归一化，避免阈值敏感。
  - 提供关键词 fallback，确保离线或加载失败仍可给出结果。

- **持久化 `db.py`**
  - 三张主要表：`posts`、`comments`、`emotions`。
  - 支持插入与查询历史记录、评论情绪分布。

- **前端 `app.py`**
  - Streamlit 多 Tab 布局，集中展示流程；
  - 使用 `matplotlib` 与 `wordcloud` 完成图表绘制；
  - 与数据库交互以支持历史回放。


## 测试与验证

- `python -m compileall weibo_sentiment`：确保所有模块语法正确。
- `python -c "from weibo_sentiment import sentiment; sentiment.predict(['太棒了！'])"`：验证模型加载。
- `python weibo_sentiment/app.py` 通过 Streamlit 接口完成端端联调。


## 已知问题与后续规划

- **抽样展示**：当前网页未对大规模评论进行分页展示，可增加分页/下载功能。
- **错误提示**：需在爬虫失败时给出更友好的提示及重试机制。
- **模型优化**：可引入专门的中文情绪分类模型或微调 pipeline，以提升准确度。
- **部署**：需要 Docker 化与更完善的日志监控以便生产部署。


## 开源协议

本仓库默认采用 MIT License（如需变更请更新许可证文件）。

