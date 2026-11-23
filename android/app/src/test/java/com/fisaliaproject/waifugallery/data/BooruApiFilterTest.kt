package com.fisaliaproject.waifugallery.data

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BooruApiFilterTest {
    @Test
    fun hidesAiGeneratedAndAssistedTagsWhenEnabled() {
        val api = BooruApi(
            useDoh = { false },
            gelbooruCredentials = { "" to "" },
            filterAiGenerated = { true },
        )

        assertFalse(api.acceptedPost(postWithTags("ai-generated")))
        assertFalse(api.acceptedPost(postWithTags("ai_assisted")))
        assertTrue(api.acceptedPost(postWithTags("1girl")))
    }

    @Test
    fun leavesAiTaggedPostsVisibleWhenDisabled() {
        val api = BooruApi(
            useDoh = { false },
            gelbooruCredentials = { "" to "" },
            filterAiGenerated = { false },
        )

        assertTrue(api.acceptedPost(postWithTags("AI-GENERATED")))
    }

    @Test
    fun removingAiFilterAllowsPreviouslyBlockedPosts() {
        var hideAiGenerated = true
        val api = BooruApi(
            useDoh = { false },
            gelbooruCredentials = { "" to "" },
            filterAiGenerated = { hideAiGenerated },
        )
        val post = postWithTags("ai-generated")

        assertFalse(api.acceptedPost(post))
        hideAiGenerated = false
        assertTrue(api.acceptedPost(post))
    }

    @Test
    fun removingCustomBlockedTagAllowsPreviouslyBlockedPosts() {
        var customBlockTags = "blue_hair"
        val api = BooruApi(
            useDoh = { false },
            gelbooruCredentials = { "" to "" },
            customBlockTags = { customBlockTags },
        )
        val post = postWithTags("blue_hair")

        assertFalse(api.acceptedPost(post))
        customBlockTags = ""
        assertTrue(api.acceptedPost(post))
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
