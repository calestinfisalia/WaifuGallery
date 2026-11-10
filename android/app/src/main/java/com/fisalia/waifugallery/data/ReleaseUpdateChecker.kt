package com.fisalia.waifugallery.data

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class ReleaseUpdate(
    val version: String,
    val notes: String,
    val apkUrl: String,
    val apkSha256: String,
)

object ReleaseUpdateChecker {
    private const val RELEASE_URL =
        "https://api.github.com/repos/calestinfisalia/WaifuGallery/releases/latest"
    private val versionPattern = Regex("^v?(\\d+(?:\\.\\d+){0,3})$", RegexOption.IGNORE_CASE)
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .callTimeout(10, TimeUnit.SECONDS)
        .build()
    private val downloadClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .callTimeout(0, TimeUnit.SECONDS)
        .build()
    private const val MAX_APK_SIZE = 512L * 1024 * 1024

    suspend fun checkForUpdate(context: Context): ReleaseUpdate? = withContext(Dispatchers.IO) {
        try {
            @Suppress("DEPRECATION")
            val currentVersionName = context.packageManager
                .getPackageInfo(context.packageName, 0)
                .versionName
                .orEmpty()
            val request = Request.Builder()
                .url(RELEASE_URL)
                .header("Accept", "application/vnd.github+json")
                .header("X-GitHub-Api-Version", "2022-11-28")
                .header("User-Agent", "WaifuGallery-Android/$currentVersionName")
                .build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext null
                val release = response.body?.string()?.let(::JSONObject) ?: return@withContext null
                if (release.optBoolean("draft", true) || release.optBoolean("prerelease", true)) {
                    return@withContext null
                }

                val tag = release.optString("tag_name")
                val currentVersion = parseVersion(currentVersionName) ?: return@withContext null
                val releaseVersion = parseVersion(tag) ?: return@withContext null
                if (compareVersions(releaseVersion, currentVersion) <= 0) return@withContext null

                val apkUrl = release.optJSONArray("assets")
                    ?.let { assets ->
                        (0 until assets.length())
                            .asSequence()
                            .mapNotNull { assets.optJSONObject(it) }
                            .firstOrNull { it.optString("name") == "app-release.apk" }
                    }
                    ?: return@withContext null
                val url = apkUrl.optString("browser_download_url")
                val digest = apkUrl.optString("digest")
                val checksum = digest.removePrefix("sha256:")
                if (!isTrustedReleaseUrl(url) || !checksum.matches(Regex("[a-fA-F0-9]{64}"))) {
                    return@withContext null
                }

                ReleaseUpdate(
                    version = tag,
                    notes = release.optString("body").trim(),
                    apkUrl = url,
                    apkSha256 = checksum,
                )
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            null
        }
    }

    suspend fun downloadApk(
        context: Context,
        update: ReleaseUpdate,
        onProgress: (Int) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        val version = update.version.removePrefix("v")
        if (!versionPattern.matches(version)) {
            throw IOException("The update version is invalid.")
        }
        if (!update.apkSha256.matches(Regex("[a-fA-F0-9]{64}"))) {
            throw IOException("The APK checksum is invalid.")
        }
        if (!isTrustedReleaseUrl(update.apkUrl)) {
            throw IOException("The APK URL is not a trusted GitHub release URL.")
        }

        val updatesDirectory = File(context.cacheDir, "updates")
        if (!updatesDirectory.exists() && !updatesDirectory.mkdirs()) {
            throw IOException("Could not create the APK download folder.")
        }
        val destination = File(updatesDirectory, "waifu-gallery-$version.apk")
        val partialFile = File(updatesDirectory, ".${UUID.randomUUID()}.part")
        try {
            val request = Request.Builder()
                .url(update.apkUrl)
                .header("Accept", "application/octet-stream")
                .header("User-Agent", "Waifu-Gallery-Android/$version")
                .build()
            downloadClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("APK download failed with HTTP ${response.code}.")
                }
                if (response.request.url.scheme != "https" ||
                    response.request.url.host !in setOf(
                        "github.com",
                        "release-assets.githubusercontent.com",
                        "objects.githubusercontent.com",
                    )
                ) {
                    throw IOException("The APK download left the trusted HTTPS hosts.")
                }
                val body = response.body ?: throw IOException("The APK download was empty.")
                val contentLength = body.contentLength()
                if (contentLength < 0 || contentLength > MAX_APK_SIZE) {
                    throw IOException("The APK is larger than the allowed download size.")
                }
                val digest = MessageDigest.getInstance("SHA-256")
                var downloaded = 0L
                body.byteStream().use { input ->
                    FileOutputStream(partialFile).use { output ->
                        val buffer = ByteArray(256 * 1024)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            downloaded += count
                            if (downloaded > MAX_APK_SIZE) {
                                throw IOException("The APK is larger than the allowed download size.")
                            }
                            digest.update(buffer, 0, count)
                            output.write(buffer, 0, count)
                            if (contentLength > 0) {
                                onProgress((downloaded * 100 / contentLength).toInt().coerceIn(0, 100))
                            }
                        }
                        output.fd.sync()
                    }
                }
                if (downloaded == 0L) throw IOException("The APK download was empty.")
                val actualDigest = digest.digest().joinToString("") { "%02x".format(it) }
                if (!actualDigest.equals(update.apkSha256, ignoreCase = true)) {
                    throw IOException("The downloaded APK failed its SHA-256 integrity check.")
                }
            }
            Files.move(
                partialFile.toPath(),
                destination.toPath(),
                StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE,
            )
            onProgress(100)
            destination
        } finally {
            if (partialFile.exists() && !partialFile.delete()) {
                throw IOException("Could not remove the incomplete APK download.")
            }
        }
    }

    private fun parseVersion(value: String): List<Long>? {
        val match = versionPattern.matchEntire(value.trim()) ?: return null
        return match.groupValues[1].split('.').map { it.toLongOrNull() ?: return null }
    }

    private fun compareVersions(left: List<Long>, right: List<Long>): Int {
        for (index in 0 until maxOf(left.size, right.size)) {
            val comparison = (left.getOrElse(index) { 0L }).compareTo(right.getOrElse(index) { 0L })
            if (comparison != 0) return comparison
        }
        return 0
    }

    private fun isTrustedReleaseUrl(value: String): Boolean {
        val url = value.toHttpUrlOrNull() ?: return false
        return url.scheme == "https" &&
            url.host == "github.com" &&
            url.encodedPath.startsWith(
                "/calestinfisalia/WaifuGallery/releases/download/",
            ) &&
            url.encodedPath.endsWith("/app-release.apk")
    }
}
