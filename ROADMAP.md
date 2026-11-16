# Waifu Gallery — Roadmap

This roadmap is an evaluation aid, not a promise or release schedule. It separates existing capabilities from possible next work. Confirm the current release/source state in the root and platform READMEs before planning a release.

## Stage 1 — MVP: browse and save media

**Status: implemented across the three platform applications, with platform-specific differences.**

- Random browsing and tag search against supported booru providers.
- Image/video display, post metadata, favorites, and downloads.
- Local preferences and basic provider/rating/media selection.
- Independent Windows, Linux, and Android applications.

**MVP acceptance:** a user can choose a supported provider, discover a post, view it, favorite it, and save it; a failed network request is not silently treated as a successful empty result.

## Stage 2 — Safety, reliability, and data portability

**Status: substantial functionality is implemented; continue platform-specific verification.**

- Provider fallback/concurrency, paging, connection diagnostics, and clearer network errors.
- Tag/rating/content filters, optional Favorites PIN, and in-app parental policy.
- Download progress/history/cancellation and richer image/video viewing.
- Encrypted cross-platform `.wgbak` version 2 with version 1 import compatibility.
- Platform-specific release checks and checksum verification.

**Exit checks:** focused tests pass on changed platforms; backup interoperability and unselected-section behavior remain intact; safety limitations are stated accurately; published assets and feed entries match.

## Stage 3 — Release quality and parity

**Suggested next priority; not all work is currently complete.**

1. **Validate each platform in its real runtime.** Exercise Linux packaging under Wayland and X11 and verify codec availability; verify Windows installer and portable packages; install and update Android on supported API levels.
2. **Harden release signing and provenance.** Replace Android debug-key release signing with a documented, protected production signing process before relying on public APK distribution. Keep signing secrets out of the repository and CI logs.
3. **Maintain a parity matrix.** Track feature availability and known differences across Windows, Linux, and Android so a platform-specific limitation is explicit rather than assumed away.
4. **Expand contract tests.** Use representative encrypted backup fixtures to verify v1 import, v2 interoperability, section selection, merge/replace semantics, and malformed-file rejection across all three implementations.
5. **Verify release pipeline end to end.** Build each artifact, inspect its version and platform, verify its digest, publish the correct platform tag, and only then update that platform's feed entry.

**Exit checks:** platform smoke tests are repeatable; release artifacts can be installed and updated; backup compatibility is covered by tests; no release manifest points to an unpublished or mismatched asset.

## Stage 4 — Maintenance and user-focused improvements

**Candidate backlog; prioritize using user feedback and reproducible issues.**

- Improve accessibility: keyboard navigation, screen-reader labels, scalable text, and sufficient contrast.
- Improve provider resilience: fixtures for schema changes, bounded retries, cancellation tests, and actionable rate-limit handling.
- Review local data lifecycle: explain credential storage, support safe credential clearing, and document backup recovery limitations.
- Reduce desktop drift by sharing tests and documenting equivalent behavior, without forcing a risky shared-code rewrite.
- Continue performance work for large favorites lists, thumbnails, and long-running downloads.

Each item should start with a concrete user need or reproducible issue. Avoid adding providers or broad architectural rewrites without evidence that they solve a priority problem.

## Deferred / out of scope unless explicitly approved

- Cloud accounts, cross-device synchronization, or remote storage of favorites and credentials.
- A shared runtime replacing the three existing platform implementations.
- Claims of complete moderation, AI classification, or OS-level parental controls.
- Automatic migration or portability for data excluded from the documented backup format.

## Planning and release notes

- Make platform scope explicit for every issue or change; update Windows and Linux together when a desktop behavior is intended to match.
- Do not infer release readiness from source version numbers. Build and verify actual artifacts first.
- Keep current published/source versions in the relevant READMEs and the authoritative release procedure in `RELEASE_UPDATE.md`.
