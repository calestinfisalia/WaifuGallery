package com.fisaliaproject.waifugallery

import androidx.compose.ui.geometry.Offset
import org.junit.Assert.assertEquals
import org.junit.Test

class ImageZoomTransformTest {
    @Test
    fun pinchKeepsTheImagePointUnderTheCentroidInPlace() {
        val viewportCenter = Offset(120f, 100f)
        val centroid = Offset(80f, 90f)
        val currentPan = Offset(8f, -12f)
        val previousZoom = 2f
        val zoomChange = 1.5f
        val panChange = Offset(5f, -3f)
        val imagePoint = Offset(
            viewportCenter.x + (centroid.x - viewportCenter.x - currentPan.x) / previousZoom,
            viewportCenter.y + (centroid.y - viewportCenter.y - currentPan.y) / previousZoom,
        )

        val newPan = panAfterCentroidZoom(
            currentPan = currentPan,
            centroid = centroid,
            viewportCenter = viewportCenter,
            zoomChange = zoomChange,
            panChange = panChange,
        )
        val newPosition = Offset(
            viewportCenter.x +
                (imagePoint.x - viewportCenter.x) * previousZoom * zoomChange + newPan.x,
            viewportCenter.y +
                (imagePoint.y - viewportCenter.y) * previousZoom * zoomChange + newPan.y,
        )

        assertEquals(centroid.x + panChange.x, newPosition.x, 0.001f)
        assertEquals(centroid.y + panChange.y, newPosition.y, 0.001f)
    }
}
