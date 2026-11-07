# Waifu Gallery

Waifu Gallery is a separate Python desktop project built around the product ideas developed for this repository: random image browsing, tag search, provider and rating filters, paged results, image zoom, credits, and downloads.

This folder has its own implementation and UI. It does not import the GTK/Android application modules or bundle their icons and mascot. It uses APIs from Danbooru and yande.re, with optional credential-based access to Gelbooru and Rule34.xxx. Provider posts and artwork remain the property of their respective creators and services; follow each provider's usage rules.

## Current features

- Windows desktop interface implemented with Python and PySide6.
- Random image browsing and tag search across Danbooru and yande.re; Gelbooru and Rule34.xxx can be enabled with your own API credentials. Selecting a provider searches only that provider. Choosing All combines available providers for search and tries providers in order for Random until an image loads.
- Rating choices for SFW, NSFW, or all results. NSFW results require enabling the option in Settings.
  - Optional tag-based gore filtering, male-only tag exclusion, and custom blocked tags configured in Settings. These filters depend on provider tags and cannot detect untagged content.
- Search gallery with 50 results per page and provider filters.
- Clicking a search result opens an in-window detail page; scroll over the image to zoom and drag to pan. Previous/next navigation works through search results and favorites. Credits appear in the app menu while a full image or video is open.
- Random and searched image/video posts, configurable in Settings. Video playback uses the built-in player and requires codecs supported by Qt Multimedia.
- Optional ambient background blur, which can be turned off in Settings.
- The toolbar download button saves the currently displayed media; the download list, progress, and clearable history are in the app menu.
- User-defined search terms used by Random.
- Icon-only toolbar actions with bundled Lucide SVG assets and tooltips; the app/window icon uses `waifugallery.ico`.
- Optional process-local DNS over HTTPS, with Cloudflare, Cloudflare Security/Family, Google Public DNS, AdGuard, and a custom RFC 8484 HTTPS endpoint.

The application only filters results using metadata provided by each image service. Always follow each provider's usage rules.

## Run on Windows

Install Python 3.10 or newer, then run:

```powershell
.\run.ps1
```

The first run creates `.venv` and installs dependencies. Later runs reuse that environment.

To build the Windows folder distribution after the first run:

```powershell
.\build_windows.ps1
```

The output is `dist\Waifu Gallery\Waifu Gallery.exe`.

The release installer and single-file portable build are generated separately from the same folder distribution. The release artifacts are written under `dist-release`.

## Provider credentials

Gelbooru is optional. Open Settings, enter your Gelbooru user ID and API key, and choose Gelbooru as the provider.

Rule34.xxx is also optional and requires its own API credentials. Sign in to Rule34.xxx, open [Account Options](https://rule34.xxx/index.php?page=account&s=options), and find the API Access Credentials section. If the API key is empty, enable the `Generate New Key?` option and save. Enter that user ID and API key in Waifu Gallery Settings, then choose Rule34.xxx. These are API credentials, not your account password.

DNS-over-HTTPS is optional. Open Settings → Network, enable it, and choose a built-in resolver or enter a custom HTTPS endpoint that supports RFC 8484 DNS wire format. Custom endpoint hostnames are bootstrapped through the system DNS resolver.

Credentials are stored for the current Windows user through `QSettings`; they are not encrypted by this application, so do not share or commit them. Rule34.xxx's [API terms](https://rule34.xxx/index.php?page=tos) prohibit ads and paywalls for apps using its API and ask clients not to hammer the service.

## Icon credits

Toolbar icons use SVG assets from [Lucide](https://github.com/lucide-icons/lucide), licensed under ISC. The application icon uses the project artwork `waifugallery.png`. The Lucide license notice is included in `waifu_gallery/assets/LUCIDE-LICENSE.txt`.

## License status

The Waifu Gallery application source code is licensed under the MIT License; see the repository [LICENSE](../LICENSE). Bundled Lucide SVGs retain their ISC and Feather-derived MIT notices in `waifu_gallery/assets/LUCIDE-LICENSE.txt`. The application logo and provider images retain their respective creators' rights and are not relicensed by the application license.
