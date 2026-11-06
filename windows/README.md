# Waifu Gallery

Waifu Gallery is a separate Python desktop project built around the product ideas developed for this repository: random image browsing, tag search, provider and rating filters, paged results, image zoom, credits, and downloads.

This folder has its own implementation and UI. It does not import the GTK/Android application modules or bundle their icons and mascot. It uses public APIs from Danbooru, yande.re, and optionally Gelbooru. Provider posts and artwork remain the property of their respective creators and services; follow each provider's usage rules.

## Current features

- Windows desktop interface implemented with Python and PySide6.
- Random image browsing and tag search across Danbooru and yande.re; Gelbooru can be enabled with your own API credentials. Selecting a provider searches only that provider. Choosing All combines available providers for search and tries providers in order for Random until an image loads.
- Rating choices for SFW, NSFW, or all results. NSFW results require enabling the option in Settings.
- Search gallery with 50 results per page and provider filters.
- Clicking a search result opens an in-window detail page with Back, credits, and download controls; scroll over the image to zoom and drag to pan. Image credits are available from the Filters/Settings menu. The random image also supports direct scroll zoom and drag panning.
- The toolbar download button saves the currently displayed image; the download list, progress, and clearable history are under Filters/Settings.
- User-defined search terms used by Random.
- Male-only tag exclusion preference.
- Icon-only toolbar actions with bundled Lucide SVG assets and tooltips; the app/window icon uses `waifugallery.png`.
- Optional Cloudflare DNS over HTTPS for provider hostname lookups.

This is an early implementation. Do not treat it as feature-complete or release-ready yet. Total-page-count display is not implemented in this project.

## Run on Windows

Install Python 3.10 or newer, then run:

```powershell
.\run.ps1
```

The first run creates `.venv` and installs dependencies. Later runs reuse that environment.

To build a Windows folder distribution after the first run:

```powershell
.\build_windows.ps1
```

The output is `dist\Waifu Gallery\Waifu Gallery.exe`.

## Gelbooru credentials

Gelbooru is optional. Open Settings, enter your Gelbooru user ID and API key, and choose Gelbooru as the provider. The values are stored for the current Windows user through `QSettings`; they are not encrypted by this application, so never share or commit them.

## Icon credits

Toolbar icons use SVG assets from [Lucide](https://github.com/lucide-icons/lucide), licensed under ISC. The application icon uses the project artwork `waifugallery.png`. The Lucide license notice is included in `waifu_gallery/assets/LUCIDE-LICENSE.txt`.

## License status

The Waifu Gallery application source code is licensed under the MIT License; see the repository [LICENSE](../LICENSE). Bundled Lucide SVGs retain their ISC and Feather-derived MIT notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. The application logo and provider images retain their respective creators' rights and are not relicensed by the application license.
