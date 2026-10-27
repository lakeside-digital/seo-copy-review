# Preserve the refined review experience

This public brief adapts Lakeside Digital's internal visual review/recreation workflow. It accompanies the working source. Client identities, research, state and internal machine paths are intentionally omitted.

## Reuse the source

Start from `index.html`, `style.css`, `app.js` and `server.py`, plus the current project brand configuration, matching input and saved backup. Preserve pending saves before edits. A screenshot alone cannot reconstruct persistence or decision semantics.

## Visual composition

- A dark page sidebar, restrained off-white workspace, visible backup/restore/export controls, source URL and current-page heading.
- Search and Pending/All/Complete/Skipped views, previous/next controls and an all-page dropdown that does not shrink with sidebar filters.
- Centered, aligned before/after page frames, approximately 340–390 px wide on desktop. Matching client branding, image crop and frame widths. Real editable text in After; immutable original text in Before.
- A suitable shared client image, labelled illustrative. No unrelated body excerpts, unrelated H2 lists or independently scrolling preview panes. Let long headings grow naturally.
- Page-copy editors near the page comparison. Before/after search previews with title/meta editors directly nearby. All supplied applicable fields remain editable, even when omitted from the simplified main preview.
- Stack at narrow widths; readable controls and no horizontal page overflow. Preserve the client's template distinctions; a captured H2 is not automatically a hero subheading.

## Decisions

Keep immutable originals, spreadsheet proposals, edited drafts and explicit decisions distinct. Navigation and autosave never approve copy. Preserve saved edits in bulk current-copy approval, preserve keep-original choices and keep skip separate from approval. Undo retains an edited draft and explicitly leaves it pending.

Completion covers required fields and edited or explicitly decided optional fields. Untouched optional fields do not block completion. Report completed, pending and skipped counts accurately; skipped can also be pending. Do not call a filtered subset the whole inventory.

Template changes require separate decisions. This public copy-only release rejects a proposed introductory subheading where no original exists; do not smuggle a structural approval into a copy action.

## Widths

Show characters and reproducible canvas estimates using Arial 20 px for titles and 14 px for descriptions. Starting targets: 580 px and 920 px. They are editorial estimates, not official Google limits. Default to warnings. A deliberately requested enforced guard is an extension: preserve legacy over-limit text, permit shortening and explicit original retention, explain rejected input and never silently truncate copy.

## Keep the reviewer in place

Same-page actions preserve document scroll, focus, expanded rationale, resized textareas and sidebar scroll. Only explicit navigation moves to another page. Test lower-page buttons while already visible; automation scrolling to locate a button is not proof that the app itself scrolled.

## Persistence and versions

Use loopback-only local serving, atomic disk writes, a serial save queue, revision conflicts, clear failed-save feedback, downloadable JSON backup and tested restore with pre-import backup. Browser local storage alone is insufficient for the approval store. Validate IDs, types and baseline version; stale tabs must not overwrite newer choices.

Resume retains decisions. New input or branding gets a new baseline and private data directory. This release deliberately blocks incompatible state rather than automatically migrating approvals; an adaptation adding migration must preserve unrelated choices, archive changed proposals and explicitly reopen affected decisions.

## Export

Resolve proposed/original/edited approvals to their corresponding exact values. Pending has no approved implementation copy. Keep draft, decision, note and implementation conditions available. The public CSV export is a long-format handoff; it does not promise source-workbook preservation. A future XLSX adapter must retain source fields, unrelated sheets, styles and formulas rather than overwrite the original workbook.

## Acceptance checks

Use disposable inputs and state. Check arbitrary page jumps save first, filters leave the all-page dropdown intact, all captured applicable fields are editable and absent fields are not invented. Check mixed decisions, edited bulk approval, explicit originals, Undo, optional completion, skip, persistence/restart, stale tabs, backup/restore and pending-safe exports. Inspect desktop and narrow layouts, image loading, heading growth and live text updates. Confirm lower-page actions preserve exact scroll and focus. Disclose untested limits.
