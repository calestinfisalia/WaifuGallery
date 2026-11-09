package com.fisalia.waifugallery.data

import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class ReleaseUpdate(
    val version: String,
    val notes: String,
    val url: String,
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

                val releasePage = release.optString("html_url")
                val apkUrl = release.optJSONArray("assets")
                    ?.let { assets ->
                        (0 until assets.length())
                            .asSequence()
                            .mapNotNull { assets.optJSONObject(it) }
                            .firstOrNull {
                                it.optString("name").endsWith(".apk", ignoreCase = true)
                            }
                            ?.optString("browser_download_url")
                    }
                    .orEmpty()
                val url = apkUrl.takeIf(::isHttpsUrl)
                    ?: releasePage.takeIf(::isHttpsUrl)
                    ?: return@withContext null

                ReleaseUpdate(
                    version = tag,
                    notes = release.optString("body").trim(),
                    url = url,
                )
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            null
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

    private fun isHttpsUrl(value: String): Boolean =
        value.startsWith("https://", ignoreCase = true)
}
