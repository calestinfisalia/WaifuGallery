package com.fisaliaproject.waifugallery.data

import java.io.IOException
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class ReleaseUpdateCheckerTest {
    private val manifest = JSONObject(
        """
        {
          "schema_version": 1,
          "platforms": {
            "windows": {"version": "0.1.13", "release_tag": "windows-v0.1.13"},
            "linux": {"version": "0.1.13", "release_tag": "linux-v0.1.13"},
            "android": {"version": "0.1.12", "release_tag": "android-v0.1.12"},
            "android_new": {"version": "0.1.13", "release_tag": "android-new-v0.1.13"}
          }
        }
        """.trimIndent(),
    )

    @Test
    fun androidUsesItsOwnManifestEntryAndVersion() {
        val target = ReleaseUpdateChecker.parseUpdateTarget(manifest, "android")

        assertEquals("0.1.12", target.version)
        assertEquals("android-v0.1.12", target.releaseTag)
        assertTrue(
            ReleaseUpdateChecker.compareVersions(
                ReleaseUpdateChecker.parseVersion(target.version)!!,
                ReleaseUpdateChecker.parseVersion("0.1.11")!!,
            ) > 0,
        )
    }

    @Test
    fun desktopVersionDoesNotMakeAndroidAppearUpdated() {
        val target = ReleaseUpdateChecker.parseUpdateTarget(manifest, "android")

        assertTrue(
            ReleaseUpdateChecker.compareVersions(
                ReleaseUpdateChecker.parseVersion(target.version)!!,
                ReleaseUpdateChecker.parseVersion("0.1.12")!!,
            ) == 0,
        )
    }

    @Test
    fun packageIdsSelectSeparateUpdateChannels() {
        assertEquals("android", updateChannelForPackageName(LEGACY_APPLICATION_ID))
        assertEquals("android_new", updateChannelForPackageName(NEW_APPLICATION_ID))
    }

    @Test
    fun updateChannelsResolveToDifferentReleaseTags() {
        val legacyTarget = ReleaseUpdateChecker.parseUpdateTarget(manifest, "android")
        val newTarget = ReleaseUpdateChecker.parseUpdateTarget(manifest, "android_new")

        assertEquals("android-v0.1.12", legacyTarget.releaseTag)
        assertEquals("android-new-v0.1.13", newTarget.releaseTag)
    }

    @Test
    fun unsupportedPackageHasNoUpdateChannel() {
        assertThrows(IOException::class.java) {
            updateChannelForPackageName("com.example.unrecognized")
        }
    }

    @Test
    fun downloadedApkMustMatchInstalledPackage() {
        requireMatchingApkPackage(NEW_APPLICATION_ID, NEW_APPLICATION_ID)
        assertThrows(IOException::class.java) {
            requireMatchingApkPackage(NEW_APPLICATION_ID, LEGACY_APPLICATION_ID)
        }
        assertThrows(IOException::class.java) {
            requireMatchingApkPackage(NEW_APPLICATION_ID, null)
        }
    }
}
