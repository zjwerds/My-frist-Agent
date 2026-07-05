import zipfile
import xml.etree.ElementTree as ET

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
        if line:
            paragraphs.append(line)

# 去重
seen = set()
unique_paragraphs = []
for p in paragraphs:
    if p not in seen:
        seen.add(p)
        unique_paragraphs.append(p)

# 写入文件
with open('resume_output.txt', 'w', encoding='utf-8') as f:
    for p in unique_paragraphs:
        f.write(p + '\n')

print(f"共提取 {len(unique_paragraphs)} 段文本，已写入 resume_output.txt")
