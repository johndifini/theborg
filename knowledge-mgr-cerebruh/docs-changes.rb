#!/usr/bin/env ruby
# frozen_string_literal: true

# Report how ../knowledge-base/docs/ differs from what has been compiled, as recorded in
# ../knowledge-base/generated-wikis/docs-manifest.tsv. Read-only: it never moves, edits,
# or records anything. INGESTING.md says what to do with each line.
#
# Output, one tab-separated line per finding (paths are relative to docs/):
#   to-organize <path>              waiting in to-organize/; file it before anything else
#   added       <path>              not in the manifest
#   updated     <path>              in the manifest with a different sha256
#   moved       <old path> <new>    same content, new path (a rename if the file name changed)
#   deleted     <path>              in the manifest, gone from docs/
#   duplicate   <name> <path> ...   one file name at several paths with identical content
# Exit status is 0 whatever it finds, 2 if the manifest is missing or malformed.

require "digest"

Encoding.default_external = Encoding::UTF_8

KB = File.expand_path("../knowledge-base", __dir__)
DOCS = File.join(KB, "docs")
MANIFEST = File.join(KB, "generated-wikis", "docs-manifest.tsv")
NOISE = [".DS_Store", ".gitkeep", "Icon\r"].freeze
# Instruction files, not docs: the projects/ folder's own and each project folder's.
# ../.bin/build-memory-inventory.py (_is_kb_doc_scaffolding) mirrors this; change both.
SCAFFOLDING = %r{\Aprojects/([^/]+/)?(AGENTS|CLAUDE)\.md\z}

# A copied imaging disc (CT, MRI) is any folder holding a DICOMDIR. Its image series,
# bundled viewer app, and autorun files are not documents; only the radiology reports
# (.pdf) and Drive links (.gdoc) inside it are. An archive (.zip) anywhere is a copy of
# files, never a doc. ../.bin/build-memory-inventory.py applies the same rule
# (_kb_disc_reason); change both together.
DISC_MARKER = "DICOMDIR"
DISC_KEEP = [".pdf", ".gdoc"].freeze

def disc_roots
  Dir.glob("**/#{DISC_MARKER}", base: DOCS).map { |rel| File.dirname(rel) }
end

def disc_content?(rel, roots)
  return true if File.extname(rel).casecmp?(".zip")
  return false if DISC_KEEP.include?(File.extname(rel).downcase)
  roots.any? { |root| root == "." || rel.start_with?("#{root}/") }
end

def current_docs
  roots = disc_roots
  Dir.glob("**/*", File::FNM_DOTMATCH, base: DOCS).sort.map do |rel|
    next unless File.file?(File.join(DOCS, rel))
    next if NOISE.include?(File.basename(rel)) || SCAFFOLDING.match?(rel)
    next if disc_content?(rel, roots)
    next if rel.split("/").any? { |part| part.start_with?(".") && part != File.basename(rel) }
    rel
  end.compact
end

unless File.file?(MANIFEST)
  warn "manifest not found: #{MANIFEST}"
  exit 2
end

recorded = {}
File.readlines(MANIFEST, chomp: true).drop(1).each_with_index do |line, i|
  next if line.strip.empty?
  path, sha, = line.split("\t")
  unless path && sha&.match?(/\A\h{64}\z/)
    warn "#{MANIFEST}:#{i + 2}: malformed row"
    exit 2
  end
  recorded[path] = sha
end

pending, compiled = current_docs.partition { |rel| rel.start_with?("to-organize/") }
pending.each { |rel| puts "to-organize\t#{rel}" }

present = compiled.to_h { |rel| [rel, Digest::SHA256.file(File.join(DOCS, rel)).hexdigest] }
gone = recorded.keys - present.keys
gone_by_sha = gone.group_by { |path| recorded[path] }

(present.keys - recorded.keys).each do |rel|
  old = gone_by_sha[present[rel]]&.shift
  if old
    gone.delete(old)
    puts "moved\t#{old}\t#{rel}"
  else
    puts "added\t#{rel}"
  end
end
(present.keys & recorded.keys).each do |rel|
  puts "updated\t#{rel}" unless present[rel] == recorded[rel]
end
gone.each { |path| puts "deleted\t#{path}" }

# Docs may share a file name in different folders (citations then name the shortest
# unique trailing path; see AGENTS.md -> Citation rules). Only identical content at
# two paths is reported: that is a copy, and the user should say which one to keep.
present.keys.group_by { |rel| [File.basename(rel), present[rel]] }.each do |(name, _), paths|
  puts "duplicate\t#{name}\t#{paths.join("\t")}" if paths.length > 1
end
