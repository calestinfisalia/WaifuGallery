# Desktop Update Information

These unreleased updates apply to the Windows, Linux, and Android applications.

## Favorites

- Added newest-first and oldest-first sorting for favorites.
- Added a local thumbnail image cache, enabled by default, to speed up loading.
- On Windows and Linux, made large Favorites windows appear sooner by building tiles in small batches, showing pending-thumbnail placeholders, and loading cached previews off the UI thread.
- On Windows and Linux, made window resizing more responsive by updating image and gallery previews during resize, then applying high-quality scaling after resizing settles.
- Moved the Favorites image count into its footer and kept Favorites downloads from automatically opening the Downloads window.
- Added Settings controls to enable or disable caching, check its disk usage, and clear cached files. Disabling the cache stops disk reads and writes but does not remove existing files.

## Settings and image viewing

- Adjusted Settings layouts so their content makes better use of the available window size.
- Long image-viewer error messages now wrap to fit instead of being clipped.
- Added an optional setting to load the original-resolution image automatically after its preview appears. It is off by default; when enabled, the manual full-image button is hidden.
- Updated the image footer: both manual and automatic loading show `Load Full Image` with animated dots, followed by the full dimensions when complete. Before loading, manual mode shows the preview dimensions; automatic mode shows `Load full size...` without full dimensions.
- Fixed Windows window stacking by clearing native owner HWNDs for non-modal app dialogs and raising the active HWND without stealing focus; Linux continues to detach transient parents. This lets the focused main window move above inactive Settings/Media Info windows without repeatedly lowering siblings.
- Enabled Windows native resize/snap styles and the custom maximize-button hit target so edge-drag snapping and Windows 11 Snap Layouts work with the frameless title bar.
- Added a fade-in when the Windows or Linux ambient background first appears; it clears while a new image is loading and returns when its preview is ready. Windows keeps blur rendering on the original label and applies fade opacity during painting to avoid nested graphics-effect compositing.
- Restored the ambient background when zooming back to fit, and preserved zoom level and pan position while the original-resolution image loads on Windows and Linux.
- Reworked detail-navigation arrows as transparent overlays on the media surface and made search pagination a compact, translucent capsule over the gallery.
- Added remembered window sizes for the main window, Favorites, Downloads, Settings, and Media Info; closing the main window now closes its open dialogs. Added minimize controls to the four dialogs and separate Windows taskbar previews grouped under the Waifu Gallery app identity.

## Verification

- Added or updated focused tests for the Windows and Linux desktop implementations.

## Android

- Added optional automatic full-resolution loading after the preview; the manual full-image action is hidden while auto-load is enabled.
- Added newest-first and oldest-first Favorites sorting and a dedicated thumbnail cache with enable, usage, and clear controls.
- Kept the preview visible and showed a wrapping error message if the full-size image fails to load.
