# Waifu Gallery

Waifu Gallery is an independent media browsing application with separate Windows, Linux, and Android implementations.

## Projects

- [Windows](windows/README.md) — Python and PySide6 desktop application (version 0.1.6).
- [Linux](linux/README.md) — Linux port of the Windows 0.1.6 desktop feature set; platform runtime and packaging still need Linux verification.
- [Android](android/README.md) — Kotlin and Jetpack Compose mobile application (version 0.1.6).

The desktop and Android applications provide random browsing, tag search, provider and rating filters, media viewing, media information, and downloads. Feature availability and platform requirements are documented in each project README.

## License and credits

The Waifu Gallery application source code is licensed under the MIT License; see [LICENSE](LICENSE). Android also includes a copy at [android/LICENSE](android/LICENSE).

The general idea of browsing random waifu images was inspired by [NyarchLinux/WaifuDownloader](https://github.com/NyarchLinux/WaifuDownloader). Waifu Gallery is an independent implementation and does not include its GTK source or artwork.

Bundled toolbar SVGs in the Windows app are from [Lucide](https://github.com/lucide-icons/lucide); their ISC and Feather-derived MIT notices are in [LUCIDE-LICENSE.txt](windows/waifu_gallery/assets/LUCIDE-LICENSE.txt). The `waifugallery.png` artwork and images fetched from providers are not relicensed by the application MIT license; their rights remain with their respective creators.

Third-party libraries retain their own licenses. Review their respective license notices when redistributing builds.

## Support

If you would like to support Waifu Gallery's development, you can do so on [Ko-fi](https://ko-fi.com/calestinfisalia).
