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
#   clash       <name> <path> ...   one file name at several paths; citations need it unique
# Exit status is 0 whatever it finds, 2 if the manifest is missing or malformed.

require "digest"

Encoding.default_external = Encoding::UTF_8

KB = File.expand_path("../knowledge-base", __dir__)
DOCS = File.join(KB, "docs")
MANIFEST = File.join(KB, "generated-wikis", "docs-manifest.tsv")
NOISE = [".DS_Store", ".gitkeep", "Icon\r"].freeze
SCAFFOLDING = ["projects/AGENTS.md", "projects/CLAUDE.md"].freeze

def current_docs
  Dir.glob("**/*", File::FNM_DOTMATCH, base: DOCS).sort.map do |rel|
    next unless File.file?(File.join(DOCS, rel))
    next if NOISE.include?(File.basename(rel)) || SCAFFOLDING.include?(rel)
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

(compiled + pending).group_by { |rel| File.basename(rel) }.each do |name, paths|
  puts "clash\t#{name}\t#{paths.join("\t")}" if paths.length > 1
end
