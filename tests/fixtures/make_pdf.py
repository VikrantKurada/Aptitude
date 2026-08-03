from pypdf import PdfWriter
def write_sample(path):
    w = PdfWriter(); w.add_blank_page(width=200, height=200)
    with open(path, "wb") as f: w.write(f)
