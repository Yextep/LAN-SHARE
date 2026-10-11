package com.brisa.app;

import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.provider.MediaStore;
import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public class BrisaDeviceTest {
    private MainActivity activity;
    private String evaluate(String script) throws Exception {
        CountDownLatch done=new CountDownLatch(1);AtomicReference<String> value=new AtomicReference<>();
        activity.runOnUiThread(() -> activity.webView.evaluateJavascript(script,result->{value.set(result);done.countDown();}));
        assertTrue("JavaScript response timed out",done.await(15,TimeUnit.SECONDS));return value.get();
    }
    private void waitFor(String expression) throws Exception {
        long deadline=System.currentTimeMillis()+45000;
        while(System.currentTimeMillis()<deadline) { if("true".equals(evaluate(expression)))return;Thread.sleep(250); }
        fail("UI condition did not become true: "+expression);
    }
    private void screenshot(String name) throws Exception {
        evaluate("document.querySelector('#toast').hidden=true");
        Thread.sleep(1200);
        ContentValues values=new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME,name);
        values.put(MediaStore.Downloads.MIME_TYPE,"image/png");
        values.put(MediaStore.Downloads.RELATIVE_PATH,"Download/");
        Uri destination=activity.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
        assertNotNull(destination);
        try(java.io.OutputStream out=activity.getContentResolver().openOutputStream(destination)) {
            InstrumentationRegistry.getInstrumentation().getUiAutomation().takeScreenshot().compress(android.graphics.Bitmap.CompressFormat.PNG,100,out);
        }
    }
    @Test public void actualAndroidTransfersThemesAndService() throws Exception {
        try(ActivityScenario<MainActivity> scenario=ActivityScenario.launch(MainActivity.class)) {
            scenario.onActivity(a->activity=a);
            long deadline=System.currentTimeMillis()+90000;
            while(activity.webView==null && System.currentTimeMillis()<deadline)Thread.sleep(250);
            assertNotNull("Android UI must initialize",activity.webView);
            waitFor("typeof uploadFiles==='function' && document.querySelector('#file-count').textContent==='0'");
            assertEquals("true",evaluate("typeof Android==='object'"));
            // Send through WebView's actual XHR, not a mocked endpoint.
            evaluate("uploadFiles([new File(['Hola desde Android'],'Notas de Brisa.txt',{type:'text/plain'}),new File(['foto'],'Recuerdos.jpg',{type:'image/jpeg'})])");
            waitFor("document.querySelectorAll('.file-row').length===2&&!uploading");
            assertEquals("true",evaluate("transfers.every(t=>t.done&&!t.error)"));
            evaluate("document.querySelector('#mkdir-button').click();document.querySelector('#folder-name').value='Fotos';document.querySelector('#folder-form').requestSubmit()");
            waitFor("document.querySelectorAll('.file-row').length===3");
            evaluate("setTheme('dark')");screenshot("brisa-android-oscuro.png");
            evaluate("setTheme('light')");screenshot("brisa-android-claro.png");
            assertEquals("true",evaluate("document.documentElement.scrollWidth<=innerWidth"));
            assertEquals("true",evaluate("localStorage.getItem('brisa-theme')==='light'"));
            assertEquals("light",activity.getSharedPreferences("brisa",android.content.Context.MODE_PRIVATE).getString("theme",""));
            evaluate("localStorage.removeItem('brisa-theme');location.reload()");
            waitFor("document.documentElement.dataset.theme==='light'&&document.querySelectorAll('.file-row').length===3");
            evaluate("showScreen('settings');document.querySelector('#readonly-toggle').click()");
            waitFor("document.querySelector('#add-files').disabled");
            evaluate("document.querySelector('#readonly-toggle').click();showScreen('home')");
            waitFor("!document.querySelector('#add-files').disabled");
            String download=BrisaRuntime.localUrl.replace("/?","/download?p=Notas%20de%20Brisa.txt&");
            HttpURLConnection connection=(HttpURLConnection)new URL(download).openConnection();
            assertEquals(200,connection.getResponseCode());
            assertEquals("Hola desde Android",new String(connection.getInputStream().readAllBytes(),StandardCharsets.UTF_8));connection.disconnect();
            ContentValues values=new ContentValues();values.put(MediaStore.Downloads.DISPLAY_NAME,"brisa-test-export.txt");values.put(MediaStore.Downloads.MIME_TYPE,"text/plain");
            Uri exported=activity.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
            assertNotNull(exported);activity.exportFile(download,exported,"brisa-test-export.txt");
            waitFor("transfers.some(t=>t.name==='brisa-test-export.txt'&&t.done)");
            try(InputStream stream=activity.getContentResolver().openInputStream(exported)) { assertEquals("Hola desde Android",new String(stream.readAllBytes(),StandardCharsets.UTF_8)); }
            activity.getContentResolver().delete(exported,null,null);
            // Native foreground lifecycle, including an explicit stop.
            InstrumentationRegistry.getInstrumentation().getUiAutomation().executeShellCommand("pm grant com.brisa.app android.permission.POST_NOTIFICATIONS").close();
            evaluate("Android.setSharing(true)");
            waitFor("sharing===true");
            assertFalse(BrisaRuntime.state(activity).optString("url").isEmpty());
            String guestUrl=BrisaRuntime.state(activity).getString("url");
            String guestLocal=guestUrl.replace(new URL(guestUrl).getHost(),"127.0.0.1");
            connection=(HttpURLConnection)new URL(guestLocal.replace("/?","/api/list?")).openConnection();assertEquals(200,connection.getResponseCode());connection.disconnect();
            evaluate("Android.setSharing(false)");waitFor("sharing===false");
            connection=(HttpURLConnection)new URL(guestLocal.replace("/?","/api/list?")).openConnection();assertEquals(401,connection.getResponseCode());connection.disconnect();
            evaluate("setTheme('dark')");
        }
    }
}
