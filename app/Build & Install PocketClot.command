#!/bin/bash
# Build + install the PocketClot app from your Mac onto a connected phone.
# Double-click in Finder to run.

set -e
cd "$(dirname "$0")"

echo "============================================="
echo " PocketClot — Build & Install"
echo "============================================="
echo ""

# JDK + Android SDK — use whatever the operator has configured globally.
export JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"

if [ ! -d "$JAVA_HOME" ]; then
    echo "ERROR: JAVA_HOME ($JAVA_HOME) does not exist."
    echo "Make sure Android Studio is installed, or set JAVA_HOME explicitly."
    read -n 1 -s -r -p "Press any key to close…"
    exit 1
fi

echo "[1/3] Gradle build …"
./gradlew :app:assembleDebug

APK="app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK" ]; then
    echo "ERROR: APK not found at $APK"
    read -n 1 -s -r -p "Press any key to close…"
    exit 1
fi
echo "✓ APK built: $APK ($(du -h "$APK" | cut -f1))"

echo ""
echo "[2/3] Checking connected devices …"
DEVICES=$(adb devices | sed -e '1d' -e '/^$/d' -e '/offline/d' -e '/unauthorized/d' | wc -l | tr -d ' ')
if [ "$DEVICES" -eq 0 ]; then
    echo "ERROR: No authorized Android device detected via adb."
    echo "USB cable? USB debugging on? Authorization prompt confirmed on the phone?"
    adb devices
    read -n 1 -s -r -p "Press any key to close…"
    exit 1
fi
echo "✓ $DEVICES device(s) detected:"
adb devices | sed '1d'

echo ""
echo "[3/3] Installing APK …"
adb install -r "$APK"

# Read the app's package name from the APK and launch it
PKG=$(aapt2 dump packagename "$APK" 2>/dev/null || aapt dump badging "$APK" 2>/dev/null | grep -o "package: name='[^']*'" | head -1 | sed "s/package: name='\([^']*\)'/\1/")
if [ -n "$PKG" ]; then
    echo "✓ Package: $PKG"
    echo ""
    echo "Launching app on the device …"
    adb shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
fi

echo ""
echo "============================================="
echo " ✓ Done! App is running on the phone."
echo "============================================="
echo ""
read -n 1 -s -r -p "Press any key to close…"
