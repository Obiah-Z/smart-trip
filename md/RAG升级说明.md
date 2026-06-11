# RAG 升级说明

## 这次做了什么

原先系统中的 `RetrievalService` 本质上是：

1. 直接读取 `backend/data/knowledge/cities.json`
2. 按城市过滤
3. 用关键词重合和少量规则排序

这属于“带一点检索味道的本地 mock”，不算真正独立的 RAG 模块。

这次已经升级为真实的本地 RAG 流程：

1. 构建独立知识语料 `backend/data/rag/corpus/manifest.json`
2. 为语料生成独立索引 `backend/data/rag/index/rag_index.json`
3. 可选生成向量索引 `backend/data/rag/index/embedding_index.json`
4. 查询时先做 query rewrite
5. 在独立语料库上执行 BM25 检索
6. 如已开启 embedding，则追加向量相似度召回并做 hybrid 融合
7. 再做业务重排与 topic 去重
8. 最终把 chunk 结果注入到规划链路

当前主知识处理链已经进一步收敛为：

`raw markdown -> chunk manifest -> bm25 index -> optional embedding index -> hybrid retrieve -> rerank`

## 新增目录

- `backend/app/rag/`
  - `corpus_builder.py`
  - `corpus_loader.py`
  - `indexer.py`
  - `retriever.py`
  - `tokenizer.py`
  - `types.py`
- `backend/data/rag/`
  - `README.md`
  - `raw_markdown/`
  - `corpus/manifest.json`
  - `index/rag_index.json`
  - `index/embedding_index.json`

## 数据来源

当前原始 Markdown 语料不是手工写死在代码里，而是由下面两份数据生成：

1. `backend/data/knowledge/cities.json`
   - 城市攻略、美食、路线、酒店区域等知识文档
2. `backend/data/mock/travel_data.json`
   - 景点、酒店、天气等结构化数据

系统先会生成 Markdown 原始语料，再从 Markdown 解析并切 chunk，例如：

- 城市某类景点总结 chunk
- 酒店安静/热闹/舒适度总结 chunk
- 天气与出行提醒 chunk

## 如何重建原始语料、chunk 与索引

在项目根目录执行：

```bash
cd backend
python scripts/build_rag_markdown_corpus.py
python scripts/build_rag_corpus.py
```

如果只想单独重建向量索引：

```bash
cd backend
python scripts/build_rag_vector_index.py
```

## 当前检索特征

当前默认使用本地 BM25 检索；如果配置了 OpenAI embedding，会自动升级为 hybrid 检索。当前具备以下特点：

- 真正独立的 Markdown 原始语料、chunk 清单和索引
- 可解释的召回过程
- 返回 `bm25_score`
- 开启 embedding 后返回 `vector_score` 与 `hybrid_score`
- 支持 query rewrite 后再检索
- 支持按城市隔离，降低跨目的地污染
- 支持按 topic 去重，提高结果覆盖面
- chunk 会继承 frontmatter 和章节 metadata

## embedding 现在怎么接了？

现在已经支持单独接入 OpenAI 官方 embedding，不影响你现有的 DeepSeek 生成链路。

配置方式：

```env
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=你的 DeepSeek Key
OPENAI_MODEL=deepseek-v4-pro

EMBEDDING_MODE=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=你的 OpenAI Key
EMBEDDING_MODEL=text-embedding-3-small
```

当前策略是：

1. 主模型继续负责规划与总结
2. embedding 模型只负责向量化知识 chunk 和查询
3. 检索层优先用 BM25 做关键词召回
4. 如向量索引可用，则再叠加语义相似度
5. 如果 embedding 请求失败，系统自动降级为 BM25，不阻塞主流程

## 还需要马上接外部向量数据库吗？

结论：暂时不需要。

当前项目规模下，本地 `embedding_index.json` 已经足够支撑：

- 小到中等规模城市攻略语料
- 混合召回验证
- 检索质量调优
- 前后端联调

只有在下面场景出现时，再考虑接入真实向量数据库更合适：

1. 文档量明显增大，单机 JSON 向量扫描开始变慢
2. 需要增量写入和在线更新知识
3. 需要多租户隔离、过滤检索或更复杂的 ANN 检索
4. 需要更完整的可观测性和线上运维能力

## 仍然可以继续升级的点

这次已经不再是 mock 检索，但还可以继续演进：

1. 接入 embedding 模型，增加向量召回
2. 增加 hybrid retrieval（BM25 + vector）
3. 增加 cross-encoder rerank
4. 接入真实外部攻略 markdown / PDF / CSV 数据源
5. 为知识源增加更新时间与来源可信度字段
6. 做离线评测集，计算 Top-K 命中率和跨城市污染率

## 现在和之前的差异

之前：

- 检索逻辑和业务逻辑耦合在一个 `RetrievalService` 文件里
- 没有独立语料目录
- 没有独立索引
- 本质是直接扫描本地 JSON

现在：

- 有独立 `rag` 包
- 有独立 `raw_markdown`、`corpus` 和 `index`
- 有独立索引构建脚本
- 检索在真正的 Markdown 切分文档集合上执行
- 返回结果里会包含 `bm25_score` 等真实检索信号
