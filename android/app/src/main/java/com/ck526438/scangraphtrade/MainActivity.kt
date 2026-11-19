package com.ck526438.scangraphtrade

import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Base64
import android.view.Gravity
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import kotlin.concurrent.thread

/**
 * Coquille Android : démarre le moteur Python (Chaquopy) qui sert l'interface sur
 * http://127.0.0.1:<port>, puis l'affiche dans une WebView. Tout reste sur le téléphone.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var splash: TextView
    private var pageReady = false
    private var pendingShare: Uri? = null
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val pickImage = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        fileCallback?.onReceiveValue(if (uri != null) arrayOf(uri) else null)
        fileCallback = null
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0B1220"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.builtInZoomControls = true
            settings.displayZoomControls = false
            addJavascriptInterface(Bridge(), "AndroidBridge")
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val url = request.url
                    if (url.host == "127.0.0.1") return false
                    startActivity(Intent(Intent.ACTION_VIEW, url))  // liens externes → navigateur
                    return true
                }

                override fun onPageFinished(view: WebView, url: String) {
                    pageReady = true
                    pendingShare?.let { sendToPage(it) }
                    pendingShare = null
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    view: WebView,
                    callback: ValueCallback<Array<Uri>>,
                    params: FileChooserParams,
                ): Boolean {
                    fileCallback?.onReceiveValue(null)
                    fileCallback = callback
                    pickImage.launch("image/*")
                    return true
                }
            }
        }
        splash = TextView(this).apply {
            text = getString(R.string.loading)
            setTextColor(Color.parseColor("#8B9BB4"))
            textSize = 16f
            gravity = Gravity.CENTER
            setBackgroundColor(Color.parseColor("#0B1220"))
        }
        setContentView(FrameLayout(this).apply {
            addView(web, ViewGroup.LayoutParams(-1, -1))
            addView(splash, ViewGroup.LayoutParams(-1, -1))
        })

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack() else finish()
            }
        })

        handleIntent(intent)
        startEngine()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun startEngine() {
        thread(name = "sgt-start") {
            try {
                if (!Python.isStarted()) Python.start(AndroidPlatform(this))
                val port = Python.getInstance().getModule("sgt_android").callAttr("start").toInt()
                Handler(Looper.getMainLooper()).post {
                    web.loadUrl("http://127.0.0.1:$port/")
                    splash.animate().alpha(0f).setDuration(250).withEndAction {
                        splash.visibility = TextView.GONE
                    }
                }
            } catch (e: Throwable) {
                Handler(Looper.getMainLooper()).post {
                    splash.text = "Impossible de démarrer le moteur :\n${e.message}"
                }
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun handleIntent(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        val uri: Uri? = if (Build.VERSION.SDK_INT >= 33) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }
        uri ?: return
        if (pageReady) sendToPage(uri) else pendingShare = uri
    }

    /** Envoie une image partagée à la page (fonction JS window.sgtReceive). */
    private fun sendToPage(uri: Uri) {
        thread {
            val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@thread
            val mime = contentResolver.getType(uri) ?: "image/png"
            val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            runOnUiThread {
                web.evaluateJavascript("window.sgtReceive('data:$mime;base64,$b64', 'capture-partagee')", null)
            }
        }
    }

    /** Fonctions appelées par la page (boutons « Exporter »). */
    inner class Bridge {
        @JavascriptInterface
        fun save(name: String, content: String, mime: String, isBase64: Boolean) {
            val bytes = if (isBase64) Base64.decode(content, Base64.DEFAULT) else content.toByteArray()
            val msg = try {
                if (Build.VERSION.SDK_INT >= 29) {
                    val values = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                        put(MediaStore.MediaColumns.MIME_TYPE, mime)
                        put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/ScanGraphTrade")
                    }
                    val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                        ?: throw IllegalStateException("stockage indisponible")
                    contentResolver.openOutputStream(uri)?.use { it.write(bytes) }
                    "Enregistré dans Téléchargements/ScanGraphTrade/$name"
                } else {
                    val dir = File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "ScanGraphTrade").apply { mkdirs() }
                    File(dir, name).writeBytes(bytes)
                    "Enregistré : ${dir.absolutePath}/$name"
                }
            } catch (e: Exception) {
                "Échec de l'enregistrement : ${e.message}"
            }
            runOnUiThread { Toast.makeText(this@MainActivity, msg, Toast.LENGTH_LONG).show() }
        }
    }
}
