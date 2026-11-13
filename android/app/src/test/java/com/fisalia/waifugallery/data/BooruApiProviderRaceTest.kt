package com.fisalia.waifugallery.data

import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

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
}
