# Project docs

Working documents for individual projects. The parent, `../../AGENTS.md`, covers the
knowledge base as a whole.

## Directory Structure

- `../` → `docs/`, all of the user's working documents.
- `<project>/` → one project's docs, in any subfolders the user likes. The folder name is
  the project's name: lowercase, with hyphens.

## How projects compile

- `docs/projects/<project>/` maps one to one to `generated-wikis/projects/<project>/`.
  Every doc in the folder feeds that sub-wiki and no other, and that sub-wiki cites no doc
  from outside the folder.
- A new project folder gets its sub-wiki at the next ingest. Renaming a project folder
  renames its sub-wiki, and deleting the folder deletes the sub-wiki.
- Material that is about a topic rather than one project belongs elsewhere in `docs/`,
  where it can feed any topic sub-wiki. Copy it in here too only if the project must
  keep its own version of it.
- These folders are for humans. Agents never edit, move, or delete the docs here; only
  an ingest run from `knowledge-mgr-cerebruh/` moves files, and only out of
  `docs/to-organize/`.
