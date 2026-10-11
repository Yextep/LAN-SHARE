#!/usr/bin/env bash
set -eu
mkdir -p docs
if (cd android && ./gradlew --no-daemon connectedDebugAndroidTest); then
    adb pull /sdcard/Download/brisa-android-oscuro.png docs/brisa-android-oscuro.png
    adb pull /sdcard/Download/brisa-android-claro.png docs/brisa-android-claro.png
else
    brisa_test_status=$?
    adb logcat -d -t 2000 > docs/android-logcat.txt
    adb shell screencap -p /sdcard/brisa-fallo.png
    adb pull /sdcard/brisa-fallo.png docs/brisa-fallo.png || true
    exit "$brisa_test_status"
fi
