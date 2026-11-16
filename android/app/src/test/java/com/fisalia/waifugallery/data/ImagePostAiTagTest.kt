package com.fisalia.waifugallery.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImagePostAiTagTest {
    @Test
    fun recognizesAiGeneratedAndAssistedTagVariantsCaseInsensitively() {
        listOf("ai-generated", "AI_GENERATED", "ai-assisted", "AI_ASSISTED")
            .forEach { tag ->
                assertTrue(postWithTags(tag).hasAiGeneratedTag())
            }
    }

    @Test
    fun doesNotMarkPostsWithoutAiTags() {
        assertFalse(postWithTags("1girl", "blue_hair").hasAiGeneratedTag())
    }

    private fun postWithTags(vararg tags: String) = ImagePost(
        id = "danbooru-1",
        dedupeKey = "danbooru:1",
        provider = "Danbooru",
        imageUrl = "https://example.invalid/image.jpg",
        thumbnailUrl = "https://example.invalid/thumbnail.jpg",
        thumbnailCandidates = listOf("https://example.invalid/thumbnail.jpg"),
        extension = "jpg",
        rating = "s",
        tags = tags.toSet(),
        source = "",
        artists = emptyList(),
    )
}
