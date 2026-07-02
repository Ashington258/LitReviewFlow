**搜索层详细步骤**（使用 Semantic Scholar + OpenAlex 为主，高度自动化、可免费/低成本实现）。

搜索层的核心目标是：**根据你的核心关键词或研究方向，自动化获取大量相关论文的元数据 + 准确的原文摘要**，供后续 LLM 处理生成引言。

### 步骤 1: 准备工作（一次设置）
1. **注册/获取凭证**（推荐）：
   - **Semantic Scholar**：访问 https://www.semanticscholar.org/product/api ，用邮箱申请免费 API Key（推荐，获得更高限额）。无需 Key 也能用，但共享限额。
   - **OpenAlex**：访问 https://openalex.org/settings/api 获取免费 API Key（每天 $1 免费额度，足够个人使用）。

2. **安装 Python 库**（推荐）：
   ```bash
   pip install requests pandas tqdm  # 基础
   # 可选：semanticscholar 官方/社区库
   ```

3. **设置 Headers**（礼貌请求，避免被限流）：
   ```python
   headers = {
       "User-Agent": "YourResearchScript/1.0 (mailto:your@email.com)",
       # Semantic Scholar 加 API Key: "x-api-key": "your_key"
   }
   ```

### 步骤 2: 构建搜索查询（核心）
- **Semantic Scholar**（适合 AI/计算机领域，相关性强）：
  - 基础搜索：`https://api.semanticscholar.org/graph/v1/paper/search`
  - 参数示例：
    ```python
    params = {
        "query": "multi-modal large language models embodied AI",  # 你的关键词
        "limit": 50,          # 单次最多 100
        "fields": "title,abstract,authors,year,venue,url,citationCount,fieldsOfStudy,openAccessPdf",
        "sort": "citationCount:desc"  # 或 "relevance" / "year:desc"
    }
    ```
  - 支持过滤：`year>2022`、`minCitationCount`、`fieldsOfStudy` 等。

- **OpenAlex**（覆盖更广，支持语义搜索）：
  - 基础搜索：`https://api.openalex.org/works`
  - 参数示例：
    ```python
    params = {
        "search": "multi-modal large language models embodied intelligence",
        "filter": "publication_year:2020-2026,type:article",  # 过滤
        "sort": "cited_by_count:desc",
        "per_page": 100,      # 最多 200
        "select": "id,title,abstract_inverted_index,authorships,publication_year,doi, cited_by_count,primary_location,concepts"
    }
    ```
  - **语义搜索**（推荐长查询）：`search.semantic=你的研究方向描述`（基于 embeddings，效果更好）。

**提示**：先用 Semantic Scholar 找高被引经典论文，再用 OpenAlex 补充最新/更全结果。

### 步骤 3: 执行搜索并处理分页
- **单页请求**：
  ```python
  import requests
  response = requests.get(url, params=params, headers=headers)
  data = response.json()
  ```

- **处理分页**（获取更多论文）：
  - Semantic Scholar：用 `offset` 参数循环（limit 最大 100）。
  - OpenAlex：用 `cursor=*` 或 `page` 参数翻页，直到 `next` 为空。
  - 示例循环（带进度条和延时）：
    ```python
    papers = []
    cursor = "*"
    while cursor:
        params["cursor"] = cursor
        resp = requests.get("https://api.openalex.org/works", params=params, headers=headers)
        results = resp.json()
        papers.extend(results.get("results", []))
        cursor = results.get("meta", {}).get("next_cursor")
        time.sleep(0.5)  # 避免限流
    ```

### 步骤 4: 提取准确原文摘要
- **Semantic Scholar**：直接在 `fields` 中请求 `"abstract"`，返回纯文本摘要。
- **OpenAlex**：返回 `abstract_inverted_index`（词位置倒排索引）。需要简单转换回文本：
  ```python
  def reconstruct_abstract(inverted_index):
      if not inverted_index:
          return "No abstract"
      words = [""] * (max(max(pos) for pos in inverted_index.values()) + 1)
      for word, positions in inverted_index.items():
          for pos in positions:
              words[pos] = word
      return " ".join(words).strip()
  ```
- 保存时同时记录 `title`、`authors`、`year`、`doi`、`url`、`citationCount` 等，便于后续排序和引用。

### 步骤 5: 结果过滤与扩展（提升质量）
- **排序/过滤**：
  - 按引用量（`citationCount` 或 `cited_by_count`）降序。
  - 按年份（最近 3-5 年 + 经典高引）。
  - 按领域（`fieldsOfStudy` 或 `concepts`）匹配你的研究方向。
- **扩展文献**（找更多相关）：
  - Semantic Scholar：用论文 ID 获取 `references` / `citations`。
  - OpenAlex：用 `referenced_works` 或作者/概念搜索。
  - 目标：每次搜索 50-200 篇，提取 Top 30-100 篇摘要。

### 步骤 6: 保存与后续对接
- 保存为 JSON / CSV / Excel：
  ```python
  import pandas as pd
  df = pd.DataFrame([{
      "title": p["title"],
      "abstract": abstract,
      "year": p["year"],
      # ... 其他字段
  } for p in papers])
  df.to_csv("literature.csv", index=False)
  df.to_json("literature.json", orient="records", force_ascii=False)
  ```
- **去重**：基于 DOI 或 Title + Year。
- 输出给 LLM：将摘要列表拼接成文本，喂给你的 AI API 生成引言。

### 实际使用建议与注意事项
- **限额处理**：
  - Semantic Scholar：无 Key 时较严，申请 Key 后稳定。
  - OpenAlex：用 Key + 合理 `per_page`，每天免费额度够抓几千条记录。
- **速率控制**：每次请求间隔 0.5-1 秒，加 `try-except` 重试 + exponential backoff。
- **多查询策略**：准备 3-5 个变体查询（关键词、同义词、英文/中文），分别跑后合并。
- **测试起步**：先用 1 个关键词跑 20 篇，确认能拿到摘要，再规模化。
- **进阶**：结合 `arxiv` API（针对预印本）或用 LangChain 的 `loaders` 进一步封装。

完成搜索层后，你会得到一个干净的**论文列表 + 原文摘要** 文件，直接输入到 LLM Prompt 中，就能高效生成“背景 → 相关工作 → 研究空白 → 本文贡献”的引言结构。

如果你提供**具体研究方向**（如关键词），我可以帮你写**完整可运行的 Python 脚本**（包含两个 API 的组合调用）。需要吗？或者需要某个 API 的详细 Prompt 示例？
