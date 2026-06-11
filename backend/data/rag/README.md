# Local RAG Data

这个目录用于存放智能旅行系统的本地 RAG 语料与索引文件。

## 目录说明

- `raw_markdown/`
  - 原始 Markdown 语料，每个城市一份主文档。
- `corpus/manifest.json`
  - 已切分后的知识 chunk 清单。
- `index/rag_index.json`
  - 基于本地 chunk 构建的 BM25 索引。
- `index/embedding_index.json`
  - 可选的本地向量索引，由 OpenAI embedding 生成。

## 知识来源

当前语料由以下两类数据生成：

1. `backend/data/knowledge/cities.json`
   - 城市攻略、路线、美食、住宿区域、人文玩法等基础知识。
2. `backend/data/mock/travel_data.json`
   - 景点、酒店、天气等结构化业务数据，会被整理成可检索文档。

## 生成方式

运行：

```bash
cd backend
python scripts/build_rag_markdown_corpus.py
python scripts/build_rag_corpus.py
```

如果只需要重建向量索引：

```bash
cd backend
python scripts/build_rag_vector_index.py
```

会自动完成：

1. 读取城市知识与结构化旅行数据
2. 生成原始 Markdown 语料
3. 基于语料和结构化知识生成 chunk 清单
4. 构建本地 BM25 索引
5. 如果开启 embedding，则额外生成向量索引

## 当前服务的场景

- 城市攻略与路线建议检索
- 酒店区域偏好检索
- 城市主题玩法检索
- 亲子、雨天、文化、citywalk 等偏好召回
- 口语化问题的语义补召回

## 后续扩展建议

- 引入真实外部 Markdown/CSV/PDF 攻略作为原始知识源
- 增加 cross-encoder rerank
- 为不同知识源保留 `source` 与 `updated_at` 元数据
