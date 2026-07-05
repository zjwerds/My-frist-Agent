import zipfile
import xml.etree.ElementTree as ET

# 定义命名空间
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
        paragraphs.append(''.join(texts))

for p in paragraphs:
    print(p)
