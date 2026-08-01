# Working from source documents

How to read authoritative documents — contracts, filings, statements, scanned
records — and cite them without drifting into invention.

**This file is reference data, not always-on context.** Read it when a task turns
on what a specific document actually says. Any agent may consult it; it is
authoritative when you do.

## Verification protocol

Citation errors are the characteristic failure here, and they are confident,
fluent, and wrong. The discipline below exists because those errors have already
been made and caught by a human reader.

1. **Verify every section citation against the source before writing it anywhere.**
   No exceptions for the "obvious" ones — those are the ones that slip.
2. **Never carry a citation forward from earlier in the conversation** without
   re-checking it against the document. Your own earlier message is not a source.
3. **Treat anything outside a verified fact base as unverified until you read it.**
   A prior summary, a filename, and a cover email are all hearsay about the
   document.
4. **When a fact is inferred rather than read, say so.** Distinguish "the document
   says" from "this appears to mean." Flag uncertainty explicitly instead of
   smoothing it over.
5. **Don't let the user sign off on a summary of a document — quote the operative
   language.** A paraphrase they approve becomes a fact they never actually checked.
6. **Read the diff, not the cover letter.** Cover letters describe documents
   inaccurately, sometimes materially.

## Extracting text

Extract the text. Do not guess at contents from a filename or a prior summary.

### `.docx`

Unzip and strip the XML:

```python
import zipfile, re
z = zipfile.ZipFile(path)
xml = z.read('word/document.xml').decode('utf-8')
xml = re.sub(r'<w:p [^>]*>|<w:p/>', '\n<P>', xml).replace('</w:p>', '\n')
text = re.sub(r'<[^>]+>', '', xml)
```

For redlines, pull the `<w:ins>` / `<w:del>` blocks separately and read
`word/comments.xml`.

### Scanned PDFs and photographed documents

These have no text layer. **Prefer a text-layer counterpart when one exists**, but
confirm the operative language against the scan — a draft that predates execution
is not the executed instrument.

`pdftoppm` and `tesseract` are **not installed** on this machine, so OCR recipes in
older notes do not run. Extract the embedded page images instead — a scan is
typically one JPEG per page:

```python
import re
data = open(path, 'rb').read()
for m in re.finditer(rb'(\d+) 0 obj\r<<(.{0,800}?)>>stream\r\n', data, re.S):
    d = m.group(2)
    if b'/Subtype/Image' not in d or b'/DCTDecode' not in d: continue
    n = int(re.search(rb'/Length (\d+)', d).group(1))
    blob = data[m.end():m.end()+n]   # zlib.decompress first if /FlateDecode precedes /DCTDecode
```

Then `sips -Z 1700` each page and read the image. Page order follows object order,
but **verify against the printed page number** — it can be offset.

**When a section number or a dollar figure matters, view the page image directly.**

### Comparison / redline PDFs

Do not parse a generated comparison PDF (Litera and similar) to determine what
changed — insertions and deletions interleave ambiguously. Compare the two
underlying drafts directly.
