import io

def rd(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()

def wr(p, t):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)

def rep(t, old, new, label):
    if "[Showing lines" in old or "[Showing lines" in t:
        raise SystemExit("truncation notice in " + label)
    if t.count(old) != 1:
        raise SystemExit("anchor count %d in %s" % (t.count(old), label))
    return t.replace(old, new)

# const.py
p = "custom_components/solar_of_things/const.py"
t = rd(p)
t = rep(t,
  '    "acInputVoltage",\r\n    "batteryDischargeCurrent",',
  '    "acInputVoltage",\r\n    "outputVoltage",\r\n    "batteryDischargeCurrent",',
  "const SENSOR_KEYS")
t = rep(t,
  '    "acInputVoltage": [\r\n        ("first", ("acInputVoltage",), 1.0),\r\n    ],',
  '    "acInputVoltage": [\r\n        ("first", ("acInputVoltage",), 1.0),\r\n    ],\r\n    # Confirmed by a live capture (per-field "unit": "V", device 517915003814383616).\r\n    "outputVoltage": [\r\n        ("first", ("outputVoltage",), 1.0),\r\n    ],',
  "const ENERGY_FLOW_RULES")
t = rep(t,
  '    "acInputVoltage": {\r\n        "name": "AC Input Voltage",\r\n        "unit": "V",\r\n        "device_class": "voltage",\r\n        "icon": "mdi:transmission-tower",\r\n    },',
  '    "acInputVoltage": {\r\n        "name": "AC Input Voltage",\r\n        "unit": "V",\r\n        "device_class": "voltage",\r\n        "icon": "mdi:transmission-tower",\r\n    },\r\n    "outputVoltage": {\r\n        "name": "Output Voltage",\r\n        "unit": "V",\r\n        "device_class": "voltage",\r\n        "icon": "mdi:power-plug",\r\n    },',
  "const SENSOR_DEFINITIONS")
wr(p, t)

# api.py
p = "custom_components/solar_of_things/api.py"
t = rd(p)
t = rep(t,
  '            "acInputVoltage",\r\n            "batteryDischargeCurrent",',
  '            "acInputVoltage",\r\n            "outputVoltage",\r\n            "batteryDischargeCurrent",',
  "api keys")
wr(p, t)

# sensor.py
p = "custom_components/solar_of_things/sensor.py"
t = rd(p)
t = rep(t,
  '    "acInputVoltage": "ac_input_voltage",',
  '    "acInputVoltage": "ac_input_voltage",\r\n    "outputVoltage": "output_voltage",',
  "sensor translations")
wr(p, t)

# strings.json + en.json
for p in ["custom_components/solar_of_things/strings.json",
          "custom_components/solar_of_things/translations/en.json"]:
    t = rd(p)
    t = rep(t,
      '      "ac_input_voltage": {\r\n        "name": "AC Input Voltage"\r\n      },',
      '      "ac_input_voltage": {\r\n        "name": "AC Input Voltage"\r\n      },\r\n      "output_voltage": {\r\n        "name": "Output Voltage"\r\n      },',
      p)
    wr(p, t)

# README.md
p = "README.md"
t = rd(p)
t = rep(t,
  '| `{device} AC Input Voltage` | V | `voltage` | AC input voltage from the utility grid |\r\n',
  '| `{device} AC Input Voltage` | V | `voltage` | AC input voltage from the utility grid |\r\n| `{device} Output Voltage` | V | `voltage` | AC output voltage delivered to loads |\r\n',
  "README")
wr(p, t)

# tests
p = "tests/test_energy_flow.py"
t = rd(p)
t = rep(t,
  '    "acInputVoltage": 231.2,\r\n    "batteryVoltage": 53.4,\r\n}',
  '    "acInputVoltage": 231.2,\r\n    "outputVoltage": 229.7,\r\n    "batteryVoltage": 53.4,\r\n}',
  "test payload")
t = rep(t,
  '    assert mapped["acInputVoltage"] == 231.2',
  '    assert mapped["acInputVoltage"] == 231.2\r\n    assert mapped["outputVoltage"] == 229.7',
  "test assertion")
wr(p, t)

print("ALL_EDITS_OK")
