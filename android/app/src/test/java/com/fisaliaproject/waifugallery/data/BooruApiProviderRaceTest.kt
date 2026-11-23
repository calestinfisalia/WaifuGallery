package com.fisaliaproject.waifugallery.data

import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.ConcurrentLinkedQueue

class BooruApiProviderRaceTest {
    @Test
    fun returnsFirstProviderWithResultsAndCancelsSlowerRequests() = runBlocking {
        var slowRequestCancelled = false
        val result = firstSuccessfulProviderResponse(
            providers = listOf("slow", "fast"),
            request = { provider ->
                if (provider == "slow") {
                    try {
                        delay(10_000)
                        listOf("slow result")
                    } finally {
                        slowRequestCancelled = true
                    }
                } else {
                    delay(10)
                    listOf("fast result")
                }
            },
            hasResult = { it.isNotEmpty() },
            onFailure = { _, _ -> },
        )

        assertEquals("fast", result?.first)
        assertEquals(listOf("fast result"), result?.second)
        assertTrue(slowRequestCancelled)
    }

    @Test
    fun skipsProviderResponsesWithoutResults() = runBlocking {
        val result = firstSuccessfulProviderResponse(
            providers = listOf("empty", "has-results"),
            request = { provider ->
                if (provider == "empty") emptyList() else listOf("image")
            },
            hasResult = { it.isNotEmpty() },
            onFailure = { _, _ -> },
        )

        assertEquals("has-results", result?.first)
        assertEquals(listOf("image"), result?.second)
    }

    @Test
    fun allProviderResponsesWaitForEveryProviderAndKeepSuccessfulResults() = runBlocking {
        val requested = ConcurrentLinkedQueue<String>()
        val errors = mutableListOf<String>()
        val results = allProviderResponses(
            providers = listOf("yande.re", "Danbooru", "Gelbooru"),
            request = { provider ->
                requested.add(provider)
                if (provider == "yande.re") delay(30)
                if (provider == "Gelbooru") error("offline")
                provider
            },
            onFailure = { provider, error -> errors += "$provider:${error.message}" },
        )

        assertEquals(setOf("yande.re", "Danbooru", "Gelbooru"), requested.toSet())
        assertEquals(listOf("yande.re", "Danbooru"), results.map { it.first })
        assertEquals(listOf("yande.re", "Danbooru"), results.map { it.second })
        assertEquals(listOf("Gelbooru:offline"), errors)
    }

    @Test
    fun allProviderPostsAreMergedRoundRobinAndDeduplicated() {
        val yandeFirst = testPost("yande.re", "y-1", "shared-first")
        val yandeDuplicate = testPost("yande.re", "y-duplicate", "shared")
        val yandeThird = testPost("yande.re", "y-3", "y-3")
        val danbooruDuplicate = testPost("Danbooru", "d-duplicate", "shared-first")
        val danbooruSecond = testPost("Danbooru", "d-2", "d-2")

        val posts = mergeProviderPostsRoundRobin(
            providerOrder = listOf("yande.re", "Danbooru"),
            postsByProvider = mapOf(
                "yande.re" to listOf(yandeFirst, yandeDuplicate, yandeThird),
                "Danbooru" to listOf(danbooruDuplicate, danbooruSecond),
            ),
            limit = 10,
        )

        assertEquals(listOf("y-1", "y-duplicate", "d-2", "y-3"), posts.map { it.id })
    }

    private fun testPost(provider: String, id: String, dedupeKey: String) = ImagePost(
        id = id,
        dedupeKey = dedupeKey,
        provider = provider,
        imageUrl = "https://example.test/$id.jpg",
        thumbnailUrl = "https://example.test/$id-thumb.jpg",
        thumbnailCandidates = emptyList(),
        extension = "jpg",
        rating = "s",
        tags = emptySet(),
        source = "",
        artists = emptyList(),
    )
}
