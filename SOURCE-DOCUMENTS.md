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

### PDFs with a text layer

Most PDFs have one. `pdftotext` is **not** installed; neither is `pypdf`. Do not
build a venv for this — macOS ships PDFKit and `swiftc` is available. Write the
extractor once into the session scratchpad:

```swift
// pdftext.swift — usage: ./pdftext <file.pdf> [firstPage] [lastPage]
import Foundation
import PDFKit
let a = CommandLine.arguments
guard a.count > 1, let doc = PDFDocument(url: URL(fileURLWithPath: a[1])) else {
    FileHandle.standardError.write("cannot open\n".data(using: .utf8)!); exit(1)
}
let first = a.count > 2 ? Int(a[2])! : 1
let last  = a.count > 3 ? min(Int(a[3])!, doc.pageCount) : doc.pageCount
FileHandle.standardError.write("pages=\(doc.pageCount)\n".data(using: .utf8)!)
for i in (first - 1)..<last {
    print("=== PAGE \(i + 1) ===")
    print(doc.page(at: i)?.string ?? "(no text layer)")
}
```

`swiftc -O pdftext.swift -o pdftext`, then `./pdftext <file> 1 8`.

`(no text layer)` on a page is the signal to switch to the scan workflow below
for that page. A page that emits text but reads as gibberish is a bad embedded
font — render it and read the image instead.

Strip NULs before grepping the output (`tr -d '\000' < out.txt > clean.txt`).
Tax and legal forms routinely contain them, and `grep` will then report "binary
file matches" and show you nothing.

**Rendering a page as an image** — for a signature block, a form box, or a page
whose text layer is unreliable — is the same framework. Prefer this over the
`/DCTDecode` object regex below, which is only needed when a document has no
text layer at all:

```swift
// pdfimg.swift — usage: ./pdfimg <file.pdf> <first> <last> [scale]
import Foundation
import PDFKit
import AppKit
let a = CommandLine.arguments
guard a.count > 3, let doc = PDFDocument(url: URL(fileURLWithPath: a[1])) else { exit(1) }
let first = Int(a[2])!, last = min(Int(a[3])!, doc.pageCount)
let scale: CGFloat = a.count > 4 ? CGFloat(Double(a[4])!) : 1.6
for i in (first - 1)..<last {
    guard let page = doc.page(at: i) else { continue }
    let r = page.bounds(for: .mediaBox)
    let sz = NSSize(width: r.width * scale, height: r.height * scale)
    let img = NSImage(size: sz)
    img.lockFocus()
    NSColor.white.setFill(); NSRect(origin: .zero, size: sz).fill()
    let ctx = NSGraphicsContext.current!.cgContext
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -r.origin.x, y: -r.origin.y)
    page.draw(with: .mediaBox, to: ctx)
    img.unlockFocus()
    let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
    try! rep.representation(using: .png, properties: [:])!
        .write(to: URL(fileURLWithPath: "page_\(i + 1).png"))
}
```

A rendered page of a personal document can carry an SSN or an account number.
Write them to the session scratchpad, never to `tmp/`, and delete them when
you are done reading.

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
