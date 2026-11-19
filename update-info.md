# Windows 0.1.26, Linux 0.1.19, and Android 0.1.31 Release Notes

Windows 0.1.26, Linux 0.1.19, and Android 0.1.31 are published. Platform versions in `updates.json` point to the latest published releases.

## Version comparison

| Platform | Previous published version | Current source version | Status |
| --- | --- | --- | --- |
| Windows | [0.1.25](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.25) | [0.1.26](https://github.com/calestinfisalia/WaifuGallery/releases/tag/windows-v0.1.26) | Published. |
| Linux | [0.1.18](https://github.com/calestinfisalia/WaifuGallery/releases/tag/linux-v0.1.18) | [0.1.19](https://github.com/calestinfisalia/WaifuGallery/releases/tag/linux-v0.1.19) | Published as x86_64 AppImage and Flatpak. |
| Android | [0.1.30](https://github.com/calestinfisalia/WaifuGallery/releases/tag/android-v0.1.30) | [0.1.31](https://github.com/calestinfisalia/WaifuGallery/releases/tag/android-v0.1.31) (`versionCode` 29) | Published. |

Windows 0.1.25 restored the opaque fullscreen photo controls while ambient backgrounds update. Linux 0.1.18 added the AI-generated content filter and Settings polish. The current desktop source adds the following changes on top of those published builds; Linux also carries the shared desktop source updates made for 0.1.19.

## New in the current desktop source

- Added provider-backed search autocomplete for eligible character and series tags. Suggestions are requested after a typing debounce and cached locally by provider and keyword prefix, separately from favorite image thumbnails.
- Added persistent offline suggestion caching and recent search history. Clicking the search field shows history; clicking a suggestion starts the search immediately.
- Added separate **General → Keyword cache** and **General → Search history** pages. Each can be cleared independently, and both can be cleared together. The existing image cache remains separate.
- Added Linux parity for the Windows autocomplete, local history, cache management, and suggestion-row controls.
- Added a dedicated tag icon for Keyword cache so it is visually distinct from Image cache.
- Added a **PNG Only** Media Type filter for provider search and random browsing. Use the provider file-type operator where supported, and verify returned file extensions; other providers return a larger candidate set for local PNG filtering. PNG format alone does not guarantee transparency.
- Reworked the Favorites filter into separate **Media type** and **Time** groups on Windows and Linux. Media choices include Show All, Image Only, Video Only, and **PNG Only (transparent)**; the selected media filter and time order persist locally.
- Added the same media and time filters to Android Favorites, including persisted filter selection. **PNG Only (transparent)** requires both a PNG file extension and the provider's `transparent_png` tag.
- Refined fullscreen desktop video controls: restore a round seek knob and use a thin gray buffered segment.

## Fixed and refined

- Fixed autocomplete dropdowns remaining visible as blank panels when the current query has no matching rows. The popup is now hidden for empty or non-matching results and filtered by the start of the query.
- Refined dropdown placement and theme styling. The popup stays aligned with the search field, keeps a consistent 4 px gap, and uses the active application theme.
- Fixed history-row delete controls so pressing the X removes the entry without starting a search.
- Improved fast window resizing: image previews use throttled, fast scaling during the drag, while final-quality rendering and gallery reflow happen after resizing settles.

## Android

Android 0.1.31 adds provider-backed search autocomplete, persistent search data, and Favorites media filters:

- Fetch character and series tag suggestions directly from the selected provider after a 180 ms debounce. Cache results by provider and keyword prefix for 24 hours, show cached matches immediately, and reuse cached suggestions offline.
- Show recent search history when the empty search field receives focus. Selecting a history item or provider suggestion starts the search in one tap; history entries can be removed from the dropdown.
- Add **Settings > Browsing > Search data** to inspect cached keyword prefixes and recent searches, then clear either collection or both. Suggestion/history storage remains separate from the image cache.
- Add a **PNG Only** media filter on desktop and Android. Provider search uses provider-supported PNG filtering and verifies file extensions; transparent-only results use the `transparent_png` tag. Favorites now have separate media-type and time filters on all three platforms.
- Published version: 0.1.31 (`versionCode` 29); the update feed now points to `android-v0.1.31`.
