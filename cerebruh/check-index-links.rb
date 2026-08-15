#!/usr/bin/env ruby
# frozen_string_literal: true

# Validate local Markdown links in every wiki index. A target must resolve exactly as
# written; extensionless links are rejected even if adding `.md` would find a page.

failures = []
checked = 0

Dir.glob("wikis/**/index.md").sort.each do |index|
  File.foreach(index).with_index(1) do |line, line_number|
    line.scan(/\[[^\]]*\]\(([^)]+)\)/) do |match|
      raw_destination = match.first.strip
      destination = if raw_destination.start_with?("<")
                      raw_destination[/\A<([^>]*)>/, 1] || raw_destination
                    else
                      raw_destination.split(/\s+/, 2).first
                    end
      next if destination.start_with?("#")
      next if destination.match?(/\A[a-z][a-z0-9+.-]*:/i)

      path_without_fragment = destination.split("#", 2).first
      resolved = File.expand_path(path_without_fragment, File.dirname(index))
      checked += 1

      next if File.exist?(resolved)

      reason = if File.file?("#{resolved}.md")
                 "missing .md extension"
               else
                 "target does not exist"
               end
      failures << "#{index}:#{line_number}: #{destination} (#{reason})"
    end
  end
end

if failures.empty?
  puts "OK: #{checked} local links across #{Dir.glob('wikis/**/index.md').length} index files"
  exit 0
end

warn failures.join("\n")
warn "FAILED: #{failures.length} of #{checked} local index links are invalid"
exit 1
