from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

try:
    import NavigationInstance
except Exception:
    NavigationInstance = None

try:
    from enigma import eInputDeviceManager
except Exception:
    eInputDeviceManager = None


class DreamNextGenInfo(Poll, Converter):
    CPU_TEMP = 0
    DDR_TEMP = 1
    REMOTE_BATTERY = 2
    REMOTE_RSSI = 3
    CURRENT_TUNER = 4

    def __init__(self, type):
        Converter.__init__(self, type)
        Poll.__init__(self)
        key = (type or "").strip().lower()
        if key == "cputemp":
            self.type = self.CPU_TEMP
        elif key == "ddrtemp":
            self.type = self.DDR_TEMP
        elif key == "remotebattery":
            self.type = self.REMOTE_BATTERY
        elif key == "currenttuner":
            self.type = self.CURRENT_TUNER
        else:
            self.type = self.REMOTE_RSSI
        self.poll_enabled = True
        self.poll_interval = 3000

    def _read_first(self, paths, scale_div=1.0, fmt="{:.0f}"):
        for path in paths:
            try:
                with open(path, "r") as f:
                    raw = f.read().strip()
                if raw == "":
                    continue
                val = float(raw)
                val = val / scale_div
                return fmt.format(val)
            except Exception:
                continue
        return None

    def _connected_remote(self):
        if eInputDeviceManager is None:
            return None
        try:
            dm = eInputDeviceManager.getInstance()
            if dm is None:
                return None
            devices = dm.getConnectedDevices()
            if not devices:
                return None
            # Prefer the first ready/connected BLE remote.
            for dev in devices:
                try:
                    if dev and dev.connected():
                        return dev
                except Exception:
                    pass
            return devices[0]
        except Exception:
            return None


    def _current_tuner_letter(self):
        try:
            slot = getattr(self.source, "slot_number", None)
            if slot is not None and int(slot) >= 0:
                return chr(ord("A") + int(slot))
        except Exception:
            pass

        candidates = []
        try:
            service = getattr(self.source, "service", None)
            if service is not None:
                candidates.append(service)
        except Exception:
            pass
        try:
            if hasattr(self.source, "getCurrentService"):
                service = self.source.getCurrentService()
                if service is not None:
                    candidates.append(service)
        except Exception:
            pass
        try:
            if NavigationInstance is not None and getattr(NavigationInstance, "instance", None) is not None:
                service = NavigationInstance.instance.getCurrentService()
                if service is not None:
                    candidates.append(service)
        except Exception:
            pass

        for service in candidates:
            try:
                feinfo = service and service.frontendInfo()
                if feinfo:
                    data = None
                    for getter in ("getFrontendData", "getAll"):
                        try:
                            fn = getattr(feinfo, getter, None)
                            if fn is None:
                                continue
                            if getter == "getAll":
                                data = fn(False)
                            else:
                                data = fn()
                            if data:
                                break
                        except Exception:
                            continue
                    if data and data.get("tuner_number") is not None:
                        slot = int(data.get("tuner_number"))
                        if slot >= 0:
                            return chr(ord("A") + slot)
                    for key in ("tuner_number", "slot_number"):
                        if data and key in data and data.get(key) is not None:
                            slot = int(data.get(key))
                            if slot >= 0:
                                return chr(ord("A") + slot)
            except Exception:
                pass
        return "--"

    @cached
    def getText(self):
        if self.type == self.CPU_TEMP:
            val = self._read_first([
                "/sys/devices/virtual/thermal/thermal_zone0/temp",
                "/proc/stb/fp/temp_sensor_avs",
                "/proc/stb/sensors/temp0/value",
                "/proc/stb/sensors/temp/value",
            ], scale_div=1000.0, fmt="{:.1f}")
            return "%s°C" % val if val else "--"
        if self.type == self.DDR_TEMP:
            val = self._read_first([
                "/sys/devices/virtual/thermal/thermal_zone1/temp",
                "/proc/stb/sensors/temp1/value",
            ], scale_div=1000.0, fmt="{:.1f}")
            return "%s°C" % val if val else "--"
        dev = self._connected_remote()
        if self.type == self.CURRENT_TUNER:
            return self._current_tuner_letter()
        if self.type == self.REMOTE_BATTERY:
            if dev is None:
                return "BAT --"
            try:
                val = dev.batteryPercent()
                if val is None or int(val) < 0:
                    return "BAT --"
                return "BAT %d%%" % int(val)
            except Exception:
                return "BAT --"
        if dev is None:
            return "RSSI --"
        try:
            rssi = dev.rssi()
            if rssi is None:
                return "RSSI --"
            return "RSSI %sdBm" % int(rssi)
        except Exception:
            return "RSSI --"

    text = property(getText)

    def changed(self, what):
        Converter.changed(self, what)
