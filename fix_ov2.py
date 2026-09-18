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

# README.md
p = "README.md"
t = rd(p)
t = rep(t,
  "| `{device} AC Input Voltage` | V | `voltage` | AC input voltage |",
  "| `{device} AC Input Voltage` | V | `voltage` | AC input voltage |\r\n| `{device} Output Voltage` | V | `voltage` | AC output voltage delivered to loads |",
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

print("OK")
