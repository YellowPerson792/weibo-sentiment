# 模块说明与改进建议

## 模块关系概览

```
 ┌──────────┐   ┌───────────┐   ┌────────┐
 │ app.py   │──▶│ crawler.py │──▶│ Weibo  │
 └────┬─────┘   └────┬──────┘   └────────┘
      │             │
      │             ▼
      │        comments + meta
      │
      ▼
 ┌──────────┐    ┌─────────────┐
 │ db.py    │ ◀─ │ sentiment.py │
 └────┬─────┘    └─────────────┘
      │
      ▼
 ┌──────────┐
 │ utils.py │  (词云/饼图等可视化)
 └──────────┘
```

1. **`app.py`**：Streamlit 入口，负责 UI、流程调度与交互逻辑。调用 `crawler` 获取数据、调用 `sentiment` 得到结果，并配合 `db` 做持久化及历史查询，最后使用 `utils` 绘图。
2. **`crawler.py`**：封装 `WeiboClient`，实现 visitor cookie 握手与评论抓取。对外暴露 `fetch_post_with_comments` 和 `get_post_meta`。
3. **`sentiment.py`**：封装 HF zero-shot pipeline，输出六情绪概率与标签，必要时回退到关键词启发式。
4. **`db.py`**：管理 SQLite，负责表初始化、插入与查询（帖子、评论、情绪分布）。保证被 `app.py` 在流程中复用。
5. **`utils.py`**：包含 `draw_pie`、`draw_wordcloud`、`tokenize` 等工具，被 `app.py` 的展示层使用。


## 模块功能详情

### app.py
- **Tab 页面**：URL 分析、文本即时分析、批量导入、历史记录。
- **流程封装**：`render_url_tab` 调用 `crawler.fetch_post_with_comments` 获取评论 -> 存库 -> 调 `sentiment.predict` -> 触发可视化。
- **结果展示**：生成 DataFrame，调用 `utils.draw_pie`、`utils.draw_wordcloud` 绘制图表。
- **依赖**：`crawler`, `sentiment`, `db`, `utils`, `pandas`.

### crawler.py
- **WeiboClient**：完成 `genvisitor` + `incarnate` 握手，注入 Referer、XSRF 头，调用 `statuses/show` 和 `comments/hotflow`。
- **数据结构**：`Comment` 数据类统一 `user/text/ts/likes`。
- **公共接口**：
  - `fetch_post_with_comments(url, max_comments)`：返回帖子元数据和评论列表。
  - `get_comments(url, max_comments)`：仅返回评论。
  - `get_post_meta(url)`：单独获取元信息。
- **工具函数**：`extract_bid`、`strip_tags`、`parse_timestamp`。

### sentiment.py
- **模型加载**：默认加载 `IDEA-CCNL/Erlangshen-RoBERTa-330M-NLI`；依赖 `transformers.pipeline`。
- **零样本推理**：将评论文本与六情绪中文标签放入 pipeline，输出 softmax 概率。
- **回退机制**：`heuristic_scores` 根据关键词统计提供兜底结果。
- **对外接口**：`predict(texts, thresh=0.5)` 返回 (probabilities, labels)。

### db.py
- **数据库文件**：默认 `weibo_sentiment/sentiment.db`。
- **表结构**：`posts`、`comments`、`emotions`、`users` (预留)。
- **核心函数**：
  - `init_db`：建表。
  - `insert_post / insert_comments / insert_emotions`。
  - `get_recent_posts`、`get_emotion_dist`、`get_comments_with_emotions`。
- **设计要点**：`posts.url` 唯一约束，避免重复插入；`emotions` 以 `comment_id` 为主键。

### utils.py
- **draw_pie**：处理情绪分布字典 -> Matplotlib 饼图。
- **draw_wordcloud**：使用 `jieba` 分词 + `WordCloud` 生成词云。
- **tokenize**：封装分词策略（无 jieba 时退回空格切分）。


## 可能的改进方向

1. **爬虫稳定性与速度**
   - 增加失败重试、代理池或多 Referer 随机化，降低被风控概率。
   - 支持并发分页抓取，针对大帖提升速度。
   - 记录抓取日志与异常，以便诊断。

2. **情绪模型优化**
   - 引入更贴近评论语境的中文情绪分类模型或微调版本。
   - 在离线模式下缓存 tokenizer/weights，减少启动耗时。
   - 增加批处理尺寸/自动分批，降低多条评论推理时的 CPU 压力。

3. **数据库与数据管理**
   - 为 `comments` 添加唯一约束（例如 `post_id + text + ts`）以去重。
   - 增加索引（如 `comments.post_id`）提升历史查询速度。
   - 引入数据导出接口（CSV/JSON）方便分享分析结果。

4. **前端体验**
   - 对评论结果表默认分页展示，并提供情绪筛选。
   - 在 URL 分析完成后自动滚动到结果区域，减少用户手动操作。
   - 在模型加载或爬虫失败时给出更友好的提示（例如“请稍候，正在下载模型”）。

5. **部署与监控**
   - 提供 Dockerfile，封装依赖与模型下载步骤。
   - 在生产环境增加鉴权和速率限制，防范滥用。
   - 打通日志系统（如 `logging` 输出到文件或 ELK）以便线上跟踪。

6. **测试与 CI**
   - 添加单元测试：例如模拟情绪预测、数据库插入/查询。
   - 引入 GitHub Actions，在推送时自动运行 lint/测试，保障质量。

以上内容可作为后续规划参考，帮助快速定位模块职责并制定优化路线。
