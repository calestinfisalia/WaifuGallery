package com.fisaliaproject.waifugallery.data

import org.junit.Assert.assertEquals
import org.junit.Test

class ImagePostFavoriteOrderingTest {
    @Test
    fun newestFirstReversesStoredInsertionOrder() {
        val posts = listOf(post("first"), post("second"), post("third"))

        assertEquals(listOf("third", "second", "first"), orderedFavorites(posts, newestFirst = true).map { it.id })
    }

    @Test
    fun oldestFirstPreservesStoredInsertionOrder() {
        val posts = listOf(post("first"), post("second"), post("third"))

        assertEquals(listOf("first", "second", "third"), orderedFavorites(posts, newestFirst = false).map { it.id })
    }

    private fun post(id: String) = ImagePost(
        id = id,
        dedupeKey = id,
        provider = "provider",
        imageUrl = "https://example.com/$id.jpg",
        thumbnailUrl = "https://example.com/$id-thumb.jpg",
        thumbnailCandidates = emptyList(),
        extension = "jpg",
        rating = "s",
        tags = emptySet(),
        source = "",
        artists = emptyList(),
    )
}
