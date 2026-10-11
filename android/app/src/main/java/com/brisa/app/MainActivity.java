package com.brisa.app;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import com.google.zxing.BarcodeFormat;
import com.google.zxing.EncodeHintType;
import com.google.zxing.MultiFormatWriter;
import com.google.zxing.common.BitMatrix;
import org.json.JSONObject;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.EnumMap;
import java.util.Map;

public final class MainActivity extends Activity {
    WebView webView;
    private LinearLayout root;
    private ValueCallback<Uri[]> fileCallback;
    private String saveUrl, saveName;
    private static final int PICK_FILES = 101, SAVE_FILE = 102;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) { saveUrl = state.getString("saveUrl"); saveName = state.getString("saveName"); }
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(Color.rgb(14,20,24));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);
        showLoading("Preparando tu brisa…", false);
        initialize();
    }
    private void initialize() {
        BrisaRuntime.worker.execute(() -> {
            try { String url = BrisaRuntime.initialize(this); runOnUiThread(() -> createWebView(url)); }
            catch (Exception error) { runOnUiThread(() -> showLoading("No se pudo iniciar Brisa. Cierra y vuelve a abrir la app.", true)); }
        });
    }
    private void showLoading(String message, boolean retry) {
        root.removeAllViews();
        TextView text = new TextView(this); text.setText(message); text.setTextColor(Color.rgb(189,255,136)); text.setTextSize(18); text.setPadding(30,80,30,30); root.addView(text);
        if (retry) { Button button = new Button(this); button.setText("Reintentar"); button.setOnClickListener(v -> { showLoading("Preparando tu brisa…", false); initialize(); }); root.addView(button); }
    }
    private void createWebView(String url) {
        if (isFinishing() || isDestroyed()) return;
        root.removeAllViews();
        webView = new WebView(this); webView.setBackgroundColor(Color.rgb(14,20,24));
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(true);
        webView.getSettings().setSupportMultipleWindows(false);
        WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0);
        webView.addJavascriptInterface(new Bridge(), "Android");
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isLocalUrl(uri.toString()) && "/".equals(uri.getPath())) return false;
                return true;
            }
            @Override public void onPageFinished(WebView view, String finishedUrl) { updateState(); }
        });
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent choose = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                try { startActivityForResult(choose, PICK_FILES); }
                catch (Exception error) { fileCallback.onReceiveValue(null); fileCallback = null; notice("No se pudo abrir el selector de archivos.", true); }
                return true;
            }
        });
        webView.setDownloadListener((downloadUrl, userAgent, disposition, mime, size) -> new Bridge().saveFile(downloadUrl, "Archivo"));
        root.addView(webView, new LinearLayout.LayoutParams(-1,-1));
        webView.loadUrl(url);
    }
    private boolean isLocalUrl(String candidate) {
        try {
            Uri uri = Uri.parse(candidate), base = Uri.parse(BrisaRuntime.localUrl);
            return "http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost()) && uri.getPort() == base.getPort()
                && base.getQueryParameter("token").equals(uri.getQueryParameter("token"));
        } catch (Exception ignored) { return false; }
    }
    void evaluate(String script) {
        runOnUiThread(() -> { if (webView != null && !isFinishing()) webView.evaluateJavascript(script, null); });
    }
    private void notice(String message, boolean error) { evaluate("window.nativeNotice&&window.nativeNotice(" + JSONObject.quote(message) + "," + error + ")"); }
    void updateState() {
        BrisaRuntime.worker.execute(() -> {
            try { JSONObject state = BrisaRuntime.state(this); evaluate("window.nativeState&&window.nativeState(" + state + ")"); }
            catch (Exception error) { notice("No se pudo consultar la conexión.", true); }
        });
    }
    public final class Bridge {
        @JavascriptInterface public void ready() { updateState(); }
        @JavascriptInterface public void closeApp() { runOnUiThread(() -> moveTaskToBack(true)); }
        @JavascriptInterface public void setSharing(boolean enabled) {
            runOnUiThread(() -> {
                try {
                    if (enabled) {
                        if (BrisaRuntime.localAddresses(MainActivity.this).isEmpty()) { notice("Conéctate a Wi-Fi o activa tu punto de acceso para compartir.", true); updateState(); return; }
                        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 103);
                        Intent service = new Intent(MainActivity.this, ShareService.class);
                        if (Build.VERSION.SDK_INT >= 26) startForegroundService(service); else startService(service);
                        webView.postDelayed(MainActivity.this::updateState, 500);
                    } else {
                        BrisaRuntime.sharing(false);
                        stopService(new Intent(MainActivity.this, ShareService.class));
                        updateState();
                    }
                } catch (Exception error) { notice("No se pudo iniciar el servicio. Vuelve a intentarlo con la app abierta.", true); updateState(); }
            });
        }
        @JavascriptInterface public void setReadOnly(boolean enabled) {
            BrisaRuntime.worker.execute(() -> {
                try { BrisaRuntime.module().callAttr("set_read_only", enabled); }
                catch (Exception error) { notice("No se pudo cambiar el modo de acceso.", true); }
            });
        }
        @JavascriptInterface public void theme(String theme) {
            runOnUiThread(() -> {
                boolean light = "light".equals(theme);
                int color = light ? Color.rgb(243,246,239) : Color.rgb(14,20,24);
                root.setBackgroundColor(color); if (webView != null) webView.setBackgroundColor(color);
                getWindow().setStatusBarColor(color); getWindow().setNavigationBarColor(color);
                int flags = light ? View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR : 0;
                if (Build.VERSION.SDK_INT >= 26 && light) flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                getWindow().getDecorView().setSystemUiVisibility(flags);
            });
        }
        @JavascriptInterface public void copyLink(String link) {
            runOnUiThread(() -> { ((ClipboardManager) getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Brisa",link)); notice("Enlace copiado.", false); });
        }
        @JavascriptInterface public void shareLink(String link) {
            runOnUiThread(() -> { try { startActivity(Intent.createChooser(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,"Abre este enlace en la misma red Wi-Fi para compartir archivos con Brisa:\n" + link), "Compartir tu brisa")); } catch (Exception e) { notice("No se pudo abrir el menú de compartir.", true); } });
        }
        @JavascriptInterface public void showQr(String link) {
            BrisaRuntime.worker.execute(() -> {
                try {
                    Map<EncodeHintType,Object> hints = new EnumMap<>(EncodeHintType.class); hints.put(EncodeHintType.MARGIN, 3);
                    BitMatrix code = new MultiFormatWriter().encode(link, BarcodeFormat.QR_CODE, 640,640,hints);
                    Bitmap bitmap = Bitmap.createBitmap(640,640,Bitmap.Config.ARGB_8888);
                    int[] pixels = new int[640*640];
                    for (int y=0;y<640;y++) for (int x=0;x<640;x++) pixels[y*640+x]=code.get(x,y)?Color.rgb(14,20,24):Color.WHITE;
                    bitmap.setPixels(pixels,0,640,0,0,640,640);
                    runOnUiThread(() -> {
                        if (isFinishing()) return;
                        ImageView image = new ImageView(MainActivity.this); image.setImageBitmap(bitmap); image.setAdjustViewBounds(true); image.setPadding(24,24,24,24);
                        new AlertDialog.Builder(MainActivity.this).setTitle("Escanea tu brisa").setMessage("Usa la cámara del otro dispositivo en la misma red Wi-Fi.").setView(image).setPositiveButton("Listo",null).show();
                    });
                } catch (Exception e) { notice("No se pudo crear el código QR.",true); }
            });
        }
        @JavascriptInterface public void openPeer(String link) {
            runOnUiThread(() -> {
                try {
                    Uri uri=Uri.parse(link);
                    if (!("http".equals(uri.getScheme()) || "https".equals(uri.getScheme())) || uri.getHost()==null || uri.getUserInfo()!=null) throw new IllegalArgumentException();
                    startActivity(new Intent(Intent.ACTION_VIEW,uri));
                } catch (Exception e) { notice("No se pudo abrir el enlace. Comprueba que tienes un navegador instalado.",true); }
            });
        }
        @JavascriptInterface public void deleteFile(String path, String name) {
            runOnUiThread(() -> new AlertDialog.Builder(MainActivity.this).setTitle("¿Eliminar de Brisa?")
                .setMessage(name + "\n\nSe eliminará esta copia de Brisa. Los archivos originales que añadiste desde tu teléfono se conservan.")
                .setNegativeButton("Cancelar", null).setPositiveButton("Eliminar", (dialog, which) ->
                    BrisaRuntime.worker.execute(() -> {
                        try { BrisaRuntime.module().callAttr("delete_path",path); evaluate("loadFiles()"); notice("Eliminado de Brisa.", false); }
                        catch (Exception error) { notice("No se pudo eliminar. El archivo podría estar en uso.", true); }
                    })).show());
        }
        @JavascriptInterface public void saveFile(String url, String filename) {
            runOnUiThread(() -> {
                Uri uri=Uri.parse(url);
                if (!isLocalUrl(url) || !("/download".equals(uri.getPath()) || "/zip".equals(uri.getPath()))) { notice("Enlace de descarga no válido.",true); return; }
                if (saveUrl != null) { notice("Termina de guardar el archivo anterior.",false); return; }
                saveUrl=url; saveName=filename.replaceAll("[\\\\/\\r\\n]","_");
                try { startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,saveName),SAVE_FILE); }
                catch (Exception e) { saveUrl=null; notice("No se pudo abrir el selector de destino.",true); }
            });
        }
    }
    void exportFile(String source, Uri destination, String name) {
        BrisaRuntime.transfers.execute(() -> {
            HttpURLConnection connection=null;
            try {
                connection=(HttpURLConnection)new URL(source).openConnection(); connection.setConnectTimeout(20000); connection.setReadTimeout(120000); connection.setInstanceFollowRedirects(false);
                if(connection.getResponseCode()!=200)throw new Exception("Error de descarga");
                try(InputStream input=connection.getInputStream(); OutputStream output=getContentResolver().openOutputStream(destination,"wt")) {
                    if(output==null)throw new Exception("Destino no disponible");
                    byte[] buffer=new byte[64*1024]; int count; while((count=input.read(buffer))!=-1)output.write(buffer,0,count);
                }
                evaluate("window.nativeSaved&&window.nativeSaved("+JSONObject.quote(name)+")");
            } catch(Exception error) {
                try { getContentResolver().delete(destination,null,null); } catch(Exception ignored) { }
                notice("No se pudo guardar el archivo. Comprueba el espacio disponible y vuelve a intentarlo.",true);
            } finally { if(connection!=null)connection.disconnect(); }
        });
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data) {
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==PICK_FILES && fileCallback!=null) {
            Uri[] results=null;
            if(resultCode==RESULT_OK && data!=null) {
                if(data.getClipData()!=null) { ClipData clip=data.getClipData(); results=new Uri[clip.getItemCount()]; for(int i=0;i<results.length;i++)results[i]=clip.getItemAt(i).getUri(); }
                else if(data.getData()!=null)results=new Uri[]{data.getData()};
            }
            fileCallback.onReceiveValue(results);fileCallback=null;
        } else if(requestCode==SAVE_FILE) {
            if(resultCode==RESULT_OK && data!=null && data.getData()!=null && saveUrl!=null)exportFile(saveUrl,data.getData(),saveName);
            saveUrl=null;saveName=null;
        }
    }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); state.putString("saveUrl",saveUrl); state.putString("saveName",saveName); }
    @Override protected void onResume() { super.onResume(); if(webView!=null) { webView.onResume(); updateState(); } }
    @Override protected void onPause() { if(webView!=null)webView.onPause(); super.onPause(); }
    @Override public void onBackPressed() { if(webView!=null)evaluate("window.nativeBack&&window.nativeBack()");else super.onBackPressed(); }
    @Override protected void onDestroy() { if(fileCallback!=null)fileCallback.onReceiveValue(null); if(webView!=null) { webView.removeJavascriptInterface("Android"); webView.destroy();webView=null; } super.onDestroy(); }
}
