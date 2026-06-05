import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "PDF body text for testing.")
doc.save("tests/fixtures/sample.pdf")
