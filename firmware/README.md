# ESP32 prototype firmware

The portable C core is shared by the native host build and the ESP-IDF project. The default backend is
emulated and requires only a USB cable. This firmware has not been built with ESP-IDF or run on hardware.

```sh
cd firmware/esp32
idf.py set-target esp32s3
idf.py build
idf.py -p PORT flash monitor
```

`idf.py set-target esp32` is also intended to configure the classic target. Protocol policy remains integer
only; emulated transport is not radio evidence.
