# Contributing

Thank you for your interest in improving Waifu Gallery. The project has
separate Windows, Linux, and Android implementations; please mention which
platforms your change affects.

## Before you start

- For bugs, search existing issues first and use the repository's bug report
  form when available.
- For larger changes, open an issue to discuss the approach before investing
  significant work.
- Keep changes focused, preserve existing behavior unless a change is intended,
  and update the relevant platform documentation.
- Never include passwords, provider API keys, personal data, or other secrets in
  issues, logs, screenshots, or commits.

## Development setup

### Windows

Use Python 3.10 or newer. From `windows`, run `.\run.ps1` in PowerShell to
create the virtual environment, install dependencies, and start the app.

### Linux

Use Python 3.10 or newer and install your distribution's Python venv support.
From `linux`, run `bash ./run.sh`. Linux desktop behavior and AppImage/Flatpak
packaging may require additional platform-specific verification.

### Android

Open the `android` directory in Android Studio, configure the Android SDK, and
let Gradle sync. To build a debug APK from PowerShell, run
`.\gradlew.bat :app:assembleDebug` from `android`.

## Changes and checks

- Run the smallest relevant build, test, or validation for your change.
- For desktop Python changes, run `python -m compileall waifu_gallery` from the
  relevant `windows` or `linux` directory.
- For Android changes, build the affected variant with Gradle and test on an
  emulator or device when practical.
- Include the commands you ran and their results in your pull request. Clearly
  note platform checks you could not perform.

## Pull requests

- Use a clear title and explain the problem and solution.
- List affected platforms, behavior changes, and validation performed.
- Include screenshots for visual changes when useful.
- Keep generated installers, APKs, caches, credentials, and machine-specific
  files out of source changes unless a maintainer specifically requests them.
- Be respectful and follow the project's [security reporting policy](SECURITY.md)
  for vulnerabilities; do not disclose vulnerability details in a public pull
  request or issue.

By submitting a contribution, you agree that it may be distributed under the
project's [MIT License](LICENSE).
