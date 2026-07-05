import zipfile
import xml.etree.ElementTree as ET
import sys
import io

# 设置标准输出为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ns = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}

with zipfile.ZipFile('resume.docx', 'r') as z:
    xml_content = z.read('word/document.xml')
    
root = ET.fromstring(xml_content)

# 提取所有文本段落
paragraphs = []
for para in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
    texts = []
    for run in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
        for t in run.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            if t.text:
                texts.append(t.text)
    if texts:
        line = ''.join(texts).strip()
        # 过滤掉完全重复的行
        if line:
            paragraphs.append(line)

# 去重并清理
seen = set()
unique_paragraphs = []
for p in paragraphs:
    if p not in seen:
        seen.add(p)
        unique_paragraphs.append(p)

for p in unique_paragraphs:
    print(p)
