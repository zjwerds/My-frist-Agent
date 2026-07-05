# FileViewer 文档预览（Word / Excel / PDF）

## 现状

FileViewer 点击文件后调用 `GET /api/files/read`，后端使用 `p.read_text("utf-8", errors="replace")` 以纯文本方式读取文件。对于 .txt、.md、.py 等文本文件正常工作，但对于：

| 格式 | 文件本质 | 当前行为 |
|---|---|---|
| .docx | ZIP 压缩包（XML 结构） | 读取到原始 ZIP 字节 → 乱码 |
| .xlsx | ZIP 压缩包（XML 结构） | 读取到原始 ZIP 字节 → 乱码 |
| .doc | 旧版二进制 OLE | 读取到二进制 → 乱码 |
| .xls | 旧版二进制 OLE | 读取到二进制 → 乱码 |
| .pdf | 结构化二进制 | 读取到二进制 → 乱码 |

## 已有基础设施

后端已有成熟的文档解析引擎 `file_parser_service.py`：

| 库 | 格式 | 解析方式 |
|---|---|---|
| PyMuPDF (`fitz`) | .pdf | get_text("text") 提取文字 |
| python-docx (`docx`) | .docx | 遍历 paragraphs 提取段落 |
| openpyxl | .xlsx | 遍历 cells，按 Sheet 组织 |

这些依赖已安装，upload 路由已在用（`POST /api/upload/parse-file`）。

## 方案

改动后端 `files.py` 中 `read_file` 函数，约 20 行：

```
files.py: read_file()
  ├── 检测 ext: .docx/.xlsx/.pdf/.doc/.xls
  │    └── p.read_bytes() → file_parser_service.parse_file()
  │         → 返回 { text, pages, size, paragraphs, ... }
  │         → 统一为 FileContent 格式返回给前端
  └── 其他 ext → 保持现有 p.read_text() 不变
```

返回格式统一，FileViewer 不需要任何修改：

```json
{
  "path": "xxx.docx",
  "name": "xxx.docx",
  "ext": ".docx",
  "size": 12345,
  "content": "(提取的纯文字内容...)",
  "truncated": false,
  "lines": 42
}
```

## 影响范围

| 文件 | 改动 | 说明 |
|---|---|---|
| `backend/app/routers/files.py` | ~20 行 | read_file 增加分支判断 |
| `frontend/src/components/RightPanel/FileViewer.tsx` | 0 行 | 返回格式兼容现有渲染 |
| 前端依赖 | 无 | 已有代码 |

## 限制

1. **.doc / .xls**（旧版 Office）：python-docx 和 openpyxl 只支持新版格式。旧版需要额外库（如 `olefile` + `antiword`），目前可返回"暂不支持旧版格式"提示
2. **扫描件 PDF**：PyMuPDF 提取不到文字 → 返回提示"建议截图后使用图片识别"
3. **排版丢失**：表格、列、缩进等格式信息会丢失，只保留纯文本结构
4. **文件大小**：解析时全量读入内存，建议限制 ≤50MB（与 upload 端点一致）

## 结论

**完全可行，改动量约 20 行后端代码，前端零改动。** 已有 `file_parser_service` 和依赖库就位，只需在 `read_file` 端点加一个按 ext 分发的分支即可。
