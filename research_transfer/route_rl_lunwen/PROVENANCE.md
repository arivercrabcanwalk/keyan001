# Provenance and Sanitization

- Export source: local project `Liu/LRPHSD` workspace, with canonical source paths recorded in `SOURCE_MANIFEST.json`.
- Evidence documents are copied from the accepted reproduction package, route-RL state/plan, weather/NFZ audits, deep-revision report, multi-objective check and E-round admission records.
- Every copied text file is SHA-256 hashed after export. The manifest is therefore a verifiable checksum of the GitHub artifact, not a checksum of the private original.
- Absolute local paths, server hostnames, remote commands, private-key material, tokens/password-like assignments and compiled binaries are removed or replaced with neutral placeholders.
- Reports retain negative results, incomplete gates and resource limitations. Sanitization must not be interpreted as a claim that the omitted server experiment is reproducible from this folder alone.
