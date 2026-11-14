package com.fisalia.waifugallery.data

import org.junit.Assert.assertEquals
import org.junit.Test

class ImagePostPreviewTest {
    @Test
    fun mediumPreviewCandidatesPreferSampleAndExcludeOriginal() {
        val post = ImagePost(
            id = "post",
            dedupeKey = "post",
            provider = "provider",
            imageUrl = "https://example.com/original.jpg",
            thumbnailUrl = "https://example.com/preview.jpg",
            thumbnailCandidates = listOf(
                "https://example.com/preview.jpg",
                "https://example.com/sample.jpg",
                "https://example.com/original.jpg",
            ),
            extension = "jpg",
            rating = "s",
            tags = emptySet(),
            source = "",
            artists = emptyList(),
            sampleUrl = "https://example.com/sample.jpg",
        )

        assertEquals(
            listOf(
                "https://example.com/sample.jpg",
                "https://example.com/preview.jpg",
            ),
            post.mediumPreviewCandidates(),
        )
    }

    @Test
    fun mediumPreviewCandidatesUseNextAvailableVariantWhenSampleIsMissing() {
        val post = ImagePost(
            id = "post",
            dedupeKey = "post",
            provider = "provider",
            imageUrl = "https://example.com/original.jpg",
            thumbnailUrl = "https://example.com/preview.jpg",
            thumbnailCandidates = listOf(
                "https://example.com/preview.jpg",
                "https://example.com/medium.jpg",
                "https://example.com/original.jpg",
            ),
            extension = "jpg",
            rating = "s",
            tags = emptySet(),
            source = "",
            artists = emptyList(),
        )

        assertEquals(
            listOf(
                "https://example.com/medium.jpg",
                "https://example.com/preview.jpg",
            ),
            post.mediumPreviewCandidates(),
        )
    }
}
