import fitz  

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

print(extract_text_from_pdf("C:\\Users\\Rahul\\Downloads\\durgashankar0112.pdf"))