# Raw Markdown Corpus

这里存放旅行系统后续用于 RAG 处理的原始 Markdown 语料。

## 结构

- 每个城市一份 Markdown 文档
- 每份文档带有 YAML frontmatter
- 文档包含：城市概览、路线建议、景点清单、餐饮、住宿、主题玩法

## Frontmatter 字段

- `doc_type`：文档类型
- `city` / `city_slug`：城市标识
- `language`：语料语言
- `source_files`：原始来源文件
- `tags`：城市主题标签
- `section_counts`：各类章节条目数
- `generated_at`：生成时间

## 生成方式

```bash
cd backend
python scripts/build_rag_markdown_corpus.py
```

## 后续建议

后续可以直接基于这些 Markdown：

1. 切 chunk
2. 提取 metadata
3. 生成向量索引或 BM25 索引
4. 增加来源时间和可信度标记

