# Set up a branded SEO copy review

Use this brief with an agent that can read local spreadsheets, edit files and run Python. Its role is to configure the review, not generate SEO recommendations.

## Starter prompt

> Set up this SEO Copy Review tool for my website using my supplied spreadsheet of existing and proposed copy and my permitted branding assets. Read README.md and RECREATION.md first. Inspect the spreadsheet and identify its page IDs, URLs and original/proposed field pairs. Map them to the supported schema in a separate values-only file without rewriting my copy or overwriting the source workbook. Preserve row identity, duplicate URL records and my scope; do not infer countries or create absent fields. Configure the client name, logo, colours, shared reference image and caption. Launch on loopback using an isolated private data directory. Verify the queue count, field coverage, live previews, saved edits, explicit approvals, skip, backup/restore and export using disposable decisions. Show me the running review and explain any unmapped fields or limitations before I start approving copy. Do not upload my spreadsheet, branding assets or decisions to a public repository or external service.

## Setup checklist

1. Inspect rather than guess column meanings. The public importer expects exact headers; create a separate mapped input if necessary. Ask only when ambiguity would alter scope or copy.
2. Preserve exact original and proposed strings. If a formula produces copy, evaluate it in the appropriate spreadsheet environment and place its verified value in the mapped input. Do not rely on stale cached results.
3. Review supported field pairs in README.md. Do not silently drop other supplied editable fields: report them and extend the schema/UI/export together if the user requests that work. Do not mistake a body H2 for a hero subheading.
4. Use actual permitted client branding. A shared image must be labelled illustrative. No client asset is bundled in the public example.
5. Keep private inputs, configuration and decisions under `private/`; image files currently live beside server.py and should use the ignored `client-*` prefix. Gitignore is a convenience, not a substitute for reviewing uploads.
6. Use a fresh data directory for a new review. Never reset an existing review to test the interface.
7. Launch with Python 3.10+; no packages to install. Do not publish or change the website as part of setup.
8. Verify visual layout at desktop and narrow widths. Confirm actual supplied fields, all-page navigation and export coverage. Report checks actually run.

The public app is a review stage. It does not perform keyword research, write recommendations, fetch pages, change the CMS or imply that pending copy is approved.
