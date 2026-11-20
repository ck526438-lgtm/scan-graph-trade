#!/usr/bin/env bash
# Installe l'APK sur l'émulateur, lui fait analyser une capture et vérifie le résultat dans logcat.
set -u
PKG=com.ck526438.scangraphtrade
DIR=/sdcard/Android/data/$PKG/files
adb install -r out/ScanGraphTrade.apk
adb shell mkdir -p $DIR
adb push assets/samples/test_axe_eurusd_m15.png $DIR/test.png
adb logcat -c
adb shell am start -n $PKG/.MainActivity --es sgt_selftest $DIR/test.png
for i in $(seq 1 60); do
  if adb logcat -d -s SGT:V | grep -q "SELFTEST"; then break; fi
  sleep 5
done
echo "----- journal de l'application -----"
adb logcat -d -s SGT:V python.stderr:V python.stdout:V AndroidRuntime:E | tail -80
LINE=$(adb logcat -d -s SGT:V | grep "SELFTEST" | tail -1)
echo "Résultat : $LINE"
echo "$LINE" | grep -q '"verdict": "\(ACHAT\|VENTE\|ATTENDRE\)"' || { echo "ÉCHEC : pas de pronostic"; exit 1; }
echo "$LINE" | grep -q '"candles": 0' && { echo "ÉCHEC : aucune bougie"; exit 1; }
exit 0
