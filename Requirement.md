## 微博评论情绪分析与可视化系统

### —— 需求说明 & 极简框架文档

---

### 1 . 项目背景与目标

* **核心任务**：对新浪微博热帖评论进行采集、六情绪多标签分析，并以图表形式可视化结果。
* **交互要求**

  1. **网址直分析**：输入微博页面 URL，系统自动爬取评论并完成情绪分析。
  2. **文本即时分析**：手动输入一条评论即可获得情绪标签与概率。
  3. **文件批量分析**：上传 CSV / XLSX / TXT，离线分析整贴评论。
* **输出要求**

  * 评论列表附情绪标签
  * ≥ 2 种图表（推荐：情绪饼图 + 词云，可扩展用户画像/地图）
  * 热帖基本信息（标题、主题、点赞/转发/评论数）
* **数据持久化**：评论及情绪结果需写入数据库供后续查询。

---

### 2 . 总体技术栈（极简版）

| 层次      | 选型                              | 用途            | 依赖包                              |
| ------- | ------------------------------- | ------------- | -------------------------------- |
| 前端 & 后端 | **Streamlit**                   | 单脚本网页、表单、图表渲染 | `streamlit`                      |
| 情绪模型    | TinyBERT-6L-768D-zh（ONNX 量化）    | 六情绪多标签推理      | `transformers` `onnxruntime`     |
| 数据采集    | `requests_html` + BeautifulSoup | 爬取微博评论        | `requests_html` `beautifulsoup4` |
| 可视化     | Matplotlib + WordCloud          | 饼图／词云         | `matplotlib` `wordcloud`         |
| 数据库     | **SQLite**                      | 持久化热帖、评论、情绪   | Python 标准库 `sqlite3`             |
| 辅助      | Pandas、jieba                    | 表格处理、中文分词     | `pandas` `jieba`                 |

全部依赖写在 `requirements.txt`，一条命令即可安装：

```bash
pip install -r requirements.txt
```

---

### 3 . 目录结构与模块职责

```
weibo_sentiment/
│  app.py          # Streamlit 入口，整合所有功能
│  crawler.py      # get_comments(url) → [{user,text,ts}]
│  sentiment.py    # predict(texts) → probs, labels
│  db.py           # SQLite 初始化与增删查
│  utils.py        # draw_pie, draw_wordcloud, 分词等
│  requirements.txt
└─ models/
   └─ tinybert-onnx/  # 量化权重 + tokenizer
```

> **单脚本即可跑**：`streamlit run app.py`

---

### 4 . 数据库设计（SQLite）

| 表            | 字段摘要                                                                 | 说明          |
| ------------ | -------------------------------------------------------------------- | ----------- |
| posts        | id, url, title, topic, like_cnt, repost_cnt, comment_cnt, created_at | 热帖信息        |
| comments     | id, post_id, user, text, ts                                          | 原始评论        |
| emotions     | comment_id, anger…surprise, top_labels                               | 六情绪概率 + 多标签 |
| users *(可选)* | id, level, region, type                                              | 供用户画像       |

---

### 5 . 业务流程

1. **输入**（URL / 文本 / 文件） →
2. **数据获取**：`crawler.py` 或 Pandas 读取 →
3. **情绪推理**：`sentiment.predict`（TinyBERT ONNX） →
4. **写库**：`db.insert_post / insert_comments / insert_emotions` →
5. **展示**：Streamlit 表格 + `utils.draw_pie/wordcloud` →
6. **持久化查询**：再次打开网页可选历史 post_id 重绘图表。

---

### 6 . 关键 API / 函数约定

| 调用点                                                      | I/O 说明                                                       |
| -------------------------------------------------------- | ------------------------------------------------------------ |
| `crawler.get_comments(url, max_comments=1000)`           | **输出**评论列表 `[{"user":…,"text":…,"ts":…}]`                    |
| `sentiment.predict(texts, thresh=0.5)`                   | **输出** `probs: List[List[float]]`, `labels: List[List[str]]` |
| `db.insert_post(meta)`                                   | 返回 `post_id`                                                 |
| `db.insert_comments(post_id, comment_list)`              | 返回最后一条 comment_id                                            |
| `db.insert_emotions(prob_list, label_list, comment_ids)` | 无返回                                                          |
| `db.get_emotion_dist(post_id)`                           | 查询六情绪分布，用于饼图                                                 |

---

### 7 . 部署与运行

```bash
# ① 安装依赖
pip install -r requirements.txt
# ② 首次运行自动下载 TinyBERT（≈120 MB）并生成 sentiment.db
streamlit run app.py
# 浏览器自动打开 http://localhost:8501
```

*若学校实验机无外网，可提前下载模型权重放入 `models/tinybert-onnx/`。*

---

### 8 . 进阶扩展（可选加分）

* **地图 / 用户画像图表**：`streamlit-echarts` + SQLite 聚合即可。
* **多线程批量推理**：`asyncio` 批处理，4 vCPU 即可 500 QPS。
* **Docker 打包**：`python:3.11-slim` 镜像 + `streamlit run` CMD，便于部署。

---

#### 完整文档至此，如需代码模板或示例 SQL，请告诉我！
