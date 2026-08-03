from ebooklib import epub
def write_sample(path):
    b = epub.EpubBook(); b.set_title("Sample Book")
    c = epub.EpubHtml(title="Chap 1", file_name="c1.xhtml")
    c.content = "<h1>Chapter 1</h1><p>Hello epub world.</p>"
    b.add_item(c); b.spine = [c]
    b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    epub.write_epub(str(path), b)
