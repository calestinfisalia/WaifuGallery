package com.fisalia.waifugallery.data

import org.json.JSONObject
import org.junit.Assert.assertEquals
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
            "android": {"version": "0.1.12", "release_tag": "android-v0.1.12"}
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
}
