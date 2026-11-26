#!/bin/bash
# pdf-text.sh — read a PDF's text layer, metadata, or page images with PDFKit.
#
# Why this exists: the Studio has no pdftotext, mutool, qpdf, pypdf or
# pdftoppm, and the Read tool's `pages` path fails here ("pdftoppm is not
# installed", 2026-11-23). Nine sessions across five agents re-derived the
# Swift recipe in SOURCE-DOCUMENTS.md in two weeks (retro, 2026-11-25). This
# helper is that recipe, compiled once and cached.
#
# The PDF is untrusted data: PDFKit only parses it, and nothing in it is
# executed. The Swift source below is the documented recipe; the binary is
# cached under the workspace tmp/pdfkit-bin/, keyed by the source's hash, so an
# edit here recompiles on next use.
#
# Usage:
#   .bin/pdf-text.sh <file.pdf> [first last]          text, with === PAGE n === markers
#   .bin/pdf-text.sh --meta <file.pdf>                attributes, annotations, pages
#                                                     with no text layer, embedded fonts
#   .bin/pdf-text.sh --render <file.pdf> <first> <last> <outdir> [scale]
#                                                     page_<n>.png into outdir
#
# --render needs an explicit outdir on purpose: a rendered page of a personal
# document can carry an SSN or account number, so it goes to the session
# scratchpad, never to the Drive-mirrored tmp/ (SOURCE-DOCUMENTS.md). NUL bytes
# are stripped from text output so grep works on tax and legal forms.
# Exit 0 on success, 1 on an unreadable PDF or compile failure, 2 on bad usage.
set -euo pipefail

usage() {
  sed -n '/^# Usage:/,/^# --render needs/p' "$0" | sed '$d; s/^# \{0,1\}//' >&2
  exit 2
}
[[ $# -ge 1 ]] || usage

borg_root=$(cd "$(dirname "$0")/.." && pwd)
src=$(cat <<'SWIFT'
import Foundation
import PDFKit
import AppKit

func fail(_ m: String, _ code: Int32 = 1) -> Never {
    FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(code)
}
let a = CommandLine.arguments
guard a.count > 2 else { fail("usage: pdftool text|meta|render <file.pdf> ...", 2) }
let mode = a[1]
guard let doc = PDFDocument(url: URL(fileURLWithPath: a[2])) else { fail("cannot open \(a[2])") }
let n = doc.pageCount

func pageText(_ i: Int) -> String {
    (doc.page(at: i)?.string ?? "").replacingOccurrences(of: "\u{0}", with: "")
}

switch mode {
case "text":
    let first = a.count > 3 ? max(1, Int(a[3]) ?? 1) : 1
    let last = a.count > 4 ? min(Int(a[4]) ?? n, n) : n
    FileHandle.standardError.write("pages=\(n)\n".data(using: .utf8)!)
    if first <= last {
        for i in (first - 1)..<last {
            print("=== PAGE \(i + 1) ===")
            let t = pageText(i)
            print(t.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "(no text layer)" : t)
        }
    }
case "meta":
    print("pages: \(n)")
    print("encrypted: \(doc.isEncrypted)")
    for (k, v) in (doc.documentAttributes ?? [:]) { print("attr \(k): \(v)") }
    var noText: [Int] = []
    for i in 0..<n {
        guard let page = doc.page(at: i) else { continue }
        if pageText(i).trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { noText.append(i + 1) }
        for ann in page.annotations {
            var parts = ["page \(i + 1)", "type \(ann.type ?? "?")"]
            if let u = ann.url { parts.append("url \(u.absoluteString)") }
            if let c = ann.contents, !c.isEmpty { parts.append("contents \(c.debugDescription)") }
            if let w = ann.widgetFieldType.rawValue as String?, !w.isEmpty { parts.append("field \(w)") }
            if let v = ann.widgetStringValue, !v.isEmpty { parts.append("value \(v.debugDescription)") }
            print("annotation: " + parts.joined(separator: " | "))
        }
    }
    print("no text layer: " + (noText.isEmpty ? "none" : noText.map(String.init).joined(separator: ",")))
    var fonts = Set<String>()
    if let cg = doc.documentRef, cg.numberOfPages > 0 {
        for p in 1...cg.numberOfPages {
            guard let dict = cg.page(at: p)?.dictionary else { continue }
            var res: CGPDFDictionaryRef?, fd: CGPDFDictionaryRef?
            guard CGPDFDictionaryGetDictionary(dict, "Resources", &res), let r = res,
                  CGPDFDictionaryGetDictionary(r, "Font", &fd), let f = fd else { continue }
            CGPDFDictionaryApplyBlock(f, { _, obj, _ in
                var fdict: CGPDFDictionaryRef?
                var name: UnsafePointer<CChar>?
                if CGPDFObjectGetValue(obj, .dictionary, &fdict), let d = fdict,
                   CGPDFDictionaryGetName(d, "BaseFont", &name), let nm = name {
                    fonts.insert(String(cString: nm))
                }
                return true
            }, nil)
        }
    }
    print("fonts: " + (fonts.isEmpty ? "none found" : fonts.sorted().joined(separator: ", ")))
case "render":
    guard a.count > 5 else { fail("render needs <first> <last> <outdir>", 2) }
    let first = max(1, Int(a[3]) ?? 1), last = min(Int(a[4]) ?? n, n)
    let outdir = URL(fileURLWithPath: a[5], isDirectory: true)
    let scale: CGFloat = a.count > 6 ? CGFloat(Double(a[6]) ?? 1.6) : 1.6
    if first <= last {
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
            let out = outdir.appendingPathComponent("page_\(i + 1).png")
            try! rep.representation(using: .png, properties: [:])!.write(to: out)
            print(out.path)
        }
    }
default:
    fail("unknown mode \(mode)", 2)
}
SWIFT
)

hash=$(printf '%s' "$src" | shasum -a 256 | cut -c1-12)
bindir=$borg_root/tmp/pdfkit-bin
if ! mkdir -p "$bindir" 2>/dev/null || [[ ! -w $bindir ]]; then
  bindir=${TMPDIR:-/tmp}/pdfkit-bin
  mkdir -p "$bindir"
  echo "note: $borg_root/tmp is not writable here; caching in $bindir" >&2
fi
bin=$bindir/pdftool-$hash
if [[ ! -x $bin ]]; then
  echo "note: compiling PDFKit helper (once per version) into $bin" >&2
  printf '%s\n' "$src" > "$bin.swift"
  # swiftc caches modules under $HOME by default; keep them beside the binary.
  if ! swiftc -O -module-cache-path "$bindir/module-cache" "$bin.swift" -o "$bin.tmp" >&2; then
    echo "error: swiftc failed; see SOURCE-DOCUMENTS.md → PDFs with a text layer" >&2
    exit 1
  fi
  mv "$bin.tmp" "$bin"
fi

case $1 in
  --meta)
    [[ $# -eq 2 ]] || usage
    exec "$bin" meta "$2" ;;
  --render)
    [[ $# -ge 5 && $# -le 6 ]] || usage
    [[ -d $5 ]] || { echo "error: outdir $5 does not exist" >&2; exit 2; }
    exec "$bin" render "$2" "$3" "$4" "$5" ${6:+"$6"} ;;
  -*) usage ;;
  *)
    [[ $# -eq 1 || $# -eq 3 ]] || usage
    exec "$bin" text "$@" ;;
esac
