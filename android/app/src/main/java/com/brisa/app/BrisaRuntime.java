package com.brisa.app;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.NetworkCapabilities;
import com.chaquo.python.Python;
import com.chaquo.python.PyObject;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.File;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class BrisaRuntime {
    static final ExecutorService worker = Executors.newSingleThreadExecutor();
    static final ExecutorService transfers = Executors.newSingleThreadExecutor();
    private static PyObject backend;
    static String localUrl;

    static synchronized String initialize(Context context) {
        if (backend == null) {
            if (!Python.isStarted()) Python.start(new AndroidPlatform(context.getApplicationContext()));
            PyObject candidate = Python.getInstance().getModule("android_backend");
            localUrl = candidate.callAttr("start", new File(context.getFilesDir(), "Brisa").getAbsolutePath()).toString();
            backend = candidate;
        }
        return localUrl;
    }
    static synchronized PyObject module() {
        if (backend == null) throw new IllegalStateException("Brisa se está preparando.");
        return backend;
    }
    static synchronized void sharing(boolean enabled) { module().callAttr("set_sharing", enabled); }
    static JSONObject state(Context context) throws Exception {
        JSONObject state = new JSONObject(module().callAttr("state").toString());
        Set<String> addresses = localAddresses(context);
        String url = "";
        if (state.optBoolean("sharing") && !addresses.isEmpty()) {
            url = "http://" + addresses.iterator().next() + ":" + state.getInt("port") + "/?token=" + state.getString("token");
        }
        state.put("url", url);
        state.remove("token");
        return state;
    }
    private static void add(Set<String> result, InetAddress address) {
        if (address instanceof Inet4Address && address.isSiteLocalAddress() && !address.isLoopbackAddress()) result.add(address.getHostAddress());
    }
    static Set<String> localAddresses(Context context) {
        Set<String> result = new LinkedHashSet<>();
        try {
            ConnectivityManager manager = (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
            for (Network network : manager.getAllNetworks()) {
                NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
                if (capabilities == null || !(capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))) continue;
                LinkProperties properties = manager.getLinkProperties(network);
                if (properties != null) for (LinkAddress address : properties.getLinkAddresses()) add(result, address.getAddress());
            }
            for (NetworkInterface network : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                String name = network.getName();
                if (!network.isUp() || !name.matches("(wlan|wifi|swlan|ap|eth|rndis).*")) continue;
                for (InetAddress address : Collections.list(network.getInetAddresses())) add(result, address);
            }
        } catch (Exception ignored) { }
        return result;
    }
}
