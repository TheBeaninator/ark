#!/bin/bash
# fetch/embedded.sh — cache the compilers that PlatformIO / arduino-cli / esp-idf normally download at install time, so firmware builds work offline.
# Boards built once: XIAO ESP32-S3/C3/C6, esp32dev, XIAO RP2040, Pico, Beetle ESP32-C3, Leonardo, Uno. Adjust the list for your hardware.
set -u; . "$(dirname "$0")/../ark.env"; log(){ echo "$(date -Is) $*"; }; A="aria2c -c -x4 --file-allocation=none --auto-file-renaming=false --console-log-level=warn"
 ────────────────────────────────────────────────────
EM=$ARK_SOFTWARE/embedded; mkdir -p $EM; log "== 5. embedded toolchains"
python3 -m venv $EM/pio-venv >/dev/null 2>&1; $EM/pio-venv/bin/pip install -q -U pip platformio >/dev/null 2>&1
export PLATFORMIO_CORE_DIR=$EM/platformio; mkdir -p $EM/pio-projects
for b in seeed_xiao_esp32s3 seeed_xiao_esp32c3 seeed_xiao_esp32c6 esp32dev seeed_xiao_rp2040 pico beetle_esp32c3 dfrobot_beetle_esp32c3 leonardo uno; do d=$EM/pio-projects/$b; mkdir -p $d/src; echo 'void setup(){} void loop(){}' > $d/src/main.cpp; printf "[env:$b]\nplatform = %s\nboard = $b\nframework = arduino\n" "$(case $b in *esp32*|beetle*|dfrobot*) echo espressif32;; *rp2040|pico) echo raspberrypi;; *) echo atmelavr;; esac)" > $d/platformio.ini; (cd $d && timeout 1800 $EM/pio-venv/bin/pio pkg install >/dev/null 2>&1 && timeout 1800 $EM/pio-venv/bin/pio run >/dev/null 2>&1) && log "  pio $b ok" || log "  pio $b FAIL (board name or toolchain)"; done
AR=$EM/arduino; mkdir -p $AR/bin; $A -d /tmp -o arduino-cli.tar.gz https://github.com/arduino/arduino-cli/releases/latest/download/arduino-cli_latest_Linux_64bit.tar.gz >/dev/null 2>&1 && tar xzf /tmp/arduino-cli.tar.gz -C $AR/bin arduino-cli
export ARDUINO_DIRECTORIES_DATA=$AR/data ARDUINO_DIRECTORIES_DOWNLOADS=$AR/downloads ARDUINO_DIRECTORIES_USER=$AR/user
$AR/bin/arduino-cli config init --overwrite >/dev/null 2>&1; $AR/bin/arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json >/dev/null 2>&1
$AR/bin/arduino-cli core update-index >/dev/null 2>&1; for c in arduino:avr esp32:esp32 rp2040:rp2040; do timeout 1800 $AR/bin/arduino-cli core install $c >/dev/null 2>&1 && log "  arduino core $c ok" || log "  arduino core $c FAIL"; done
IDF=$ARK_SOFTWARE/src/github.com__espressif__esp-idf; export IDF_TOOLS_PATH=$EM/esp-idf-tools; mkdir -p $IDF_TOOLS_PATH
[ -f $IDF/install.sh ] && (cd $IDF && timeout 3600 ./install.sh esp32,esp32s3,esp32c3,esp32c6 >/dev/null 2>&1) && log "  esp-idf tools ok" || log "  esp-idf tools FAIL"
cat > $EM/README.md <<'R'
# Embedded toolchains (offline). platformio: PLATFORMIO_CORE_DIR=<here>/platformio + pio-venv (platforms espressif32, raspberrypi, atmelavr with toolchains; example projects in pio-projects/ built once).
arduino: ARDUINO_DIRECTORIES_DATA=<here>/arduino/data (cores arduino:avr esp32:esp32 rp2040:rp2040 + their compilers), bin/arduino-cli.
esp-idf: IDF_TOOLS_PATH=<here>/esp-idf-tools; source software/src/github.com__espressif__esp-idf/export.sh with that env.  Set PLATFORMIO_CORE_DIR / ARDUINO_DIRECTORIES_* / IDF_TOOLS_PATH on the island and everything resolves locally.
R
log "  embedded: $(du -sh $EM | cut -f1)"

