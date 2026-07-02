# LitReviewFlow

LitReviewFlow 是一个自动化文献检索与摘要接口服务。它从 OpenAlex 和 Semantic Scholar 检索论文，统一输出标题、作者、年份、DOI、链接、引用数、开放 PDF、完整摘要等字段，并提供 OpenAPI/HTTP 接口给其他 AI 调用。

完整使用说明见 [doc/使用文档.md](doc/使用文档.md)。

## 快速启动

```powershell
python -m pip install -r requirements.txt
Copy-Item config/config.example.json config/config.json
python -m uvicorn litreviewflow.api:app --host 127.0.0.1 --port 8000
```

`config/config.json` 是本地配置文件，可填写 OpenAlex 与 Semantic Scholar API Key；该文件包含密钥，不会提交到 Git。公开仓库只保留 `config/config.example.json` 作为配置结构模板。

## 命令行检索

```powershell
python scripts/search_literature.py "field-oriented control FOC motor drive PMSM" --limit 10
```

DOI 精确回查英文摘要：

```powershell
python scripts/search_literature.py --doi "10.1117/1.2399537" --providers openalex --output english
```

AI 友好接口：

```text
GET http://127.0.0.1:8000/ai/literature/search?query=field-oriented%20control%20FOC&limit=10
```

DOI 精确接口：

```text
GET http://127.0.0.1:8000/ai/literature/doi?doi=10.1117/1.2399537&providers=openalex
```

## 测试

```powershell
python -m pytest
```
