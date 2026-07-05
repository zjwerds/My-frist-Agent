import zipfile

with open('resume.docx', 'rb') as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
print(f"First bytes: {data[:20].hex()}")

try:
    with zipfile.ZipFile('resume.docx', 'r') as z:
        names = z.namelist()
        print(f"Files in archive ({len(names)}):")
        for name in names:
            info = z.getinfo(name)
            print(f"  {name} ({info.file_size} bytes)")
        
        # Try to read document.xml
        if 'word/document.xml' in names:
            print("\n--- word/document.xml ---")
            content = z.read('word/document.xml')
            print(content[:2000].decode('utf-8', errors='replace'))
except Exception as e:
    print(f"Zip error: {e}")
    print("Not a valid zip/docx file")
