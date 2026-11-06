# Waifu Gallery

Waifu Gallery is an independent image browsing application with separate Windows and Android implementations.

## Projects

- [Windows](windows/README.md) — Python and PySide6 desktop application.
- [Linux](linux/README.md) — separate Linux porting workspace copied from the Windows implementation; not yet release-ready.
- [Android](android/README.md) — Kotlin and Jetpack Compose mobile application.

Both applications provide random image browsing, tag search, provider and rating filters, image viewing, credits, and downloads. Features and platform requirements are documented in each project README.

## License and credits

The Waifu Gallery application source code is licensed under the MIT License; see [LICENSE](LICENSE). Android also includes a copy at [android/LICENSE](android/LICENSE).

The general idea of browsing random waifu images was inspired by [NyarchLinux/WaifuDownloader](https://github.com/NyarchLinux/WaifuDownloader). Waifu Gallery is an independent implementation and does not include its GTK source or artwork.

Bundled toolbar SVGs in the Windows app are from [Lucide](https://github.com/lucide-icons/lucide); their ISC and Feather-derived MIT notices are in [LUCIDE-LICENSE.txt](windows/waifu_gallery/assets/LUCIDE-LICENSE.txt). The `waifugallery.png` artwork and images fetched from providers are not relicensed by the application MIT license; their rights remain with their respective creators.

Third-party libraries retain their own licenses. Review their respective license notices when redistributing builds.

## Support

If you would like to support Waifu Gallery's development, you can do so on [Ko-fi](https://ko-fi.com/calestinfisalia).
