package com.ck526438.scangraphtrade

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import org.json.JSONArray
import org.json.JSONObject

/**
 * OCR sur le téléphone (Google ML Kit, modèle intégré à l'APK : fonctionne hors ligne).
 * Appelé depuis Python (sgt_android.py) à la place de Tesseract : lit l'axe des prix et
 * l'en-tête (symbole, unité de temps) de la capture.
 */
object OcrHelper {
    private val recognizer by lazy { TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS) }

    /** Renvoie un tableau JSON de mots : [{"text", "x", "y", "w", "h"}] en pixels de l'image d'origine. */
    @JvmStatic
    fun recognize(bytes: ByteArray): String {
        val src = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return "[]"
        // les petites graduations se lisent mieux agrandies
        val scale = if (src.width < 1800) 2 else 1
        val bmp = if (scale > 1) Bitmap.createScaledBitmap(src, src.width * scale, src.height * scale, true) else src
        val result = Tasks.await(recognizer.process(InputImage.fromBitmap(bmp, 0)))
        val out = JSONArray()
        for (block in result.textBlocks) for (line in block.lines) for (el in line.elements) {
            val b = el.boundingBox ?: continue
            out.put(
                JSONObject()
                    .put("text", el.text)
                    .put("x", b.left / scale)
                    .put("y", b.top / scale)
                    .put("w", b.width() / scale)
                    .put("h", b.height() / scale)
            )
        }
        return out.toString()
    }
}
