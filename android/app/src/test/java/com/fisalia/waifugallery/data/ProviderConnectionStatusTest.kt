package com.fisalia.waifugallery.data

import org.junit.Assert.assertEquals
import org.junit.Test

class ProviderConnectionStatusTest {
    @Test
    fun formatsHealthyAndRateLimitedResponses() {
        assertEquals("HTTP 200 - Connection healthy", formatProviderHttpStatus(200))
        assertEquals("HTTP 429 - Rate limited; retry later", formatProviderHttpStatus(429))
    }

    @Test
    fun preservesUnexpectedHttpReason() {
        assertEquals(
            "HTTP 418 - I'm a teapot",
            formatProviderHttpStatus(418, "I'm a teapot"),
        )
    }
}
