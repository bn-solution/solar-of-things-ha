import io

def rd(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()

def wr(p, t):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)

def rep(t, old, new, label):
    if t.count(old) != 1:
        raise SystemExit("anchor count %d in %s" % (t.count(old), label))
    return t.replace(old, new)

NL = "\r\n"
p = "custom_components/solar_of_things/sensor.py"
t = rd(p)

t = rep(t,
  '            if key.startswith("monthly_"):' + NL + '                continue',
  '            if key.startswith("monthly_") or key.startswith("station_"):' + NL + '                continue',
  "sensor per-device loop")

t = rep(t,
  '            if not key.startswith("monthly_"):' + NL + '                continue',
  '            if not (key.startswith("monthly_") or key.startswith("station_")):' + NL + '                continue',
  "sensor station loop")

t = rep(t,
  '    "ntcMaximumTemperature": "ntc_maximum_temperature",',
  '    "ntcMaximumTemperature": "ntc_maximum_temperature",' + NL +
  '    "station_daily_production": "station_daily_production",' + NL +
  '    "station_yearly_production": "station_yearly_production",' + NL +
  '    "station_total_production": "station_total_production",' + NL +
  '    "station_producing_power": "station_producing_power",' + NL +
  '    "station_total_earnings": "station_total_earnings",' + NL +
  '    "station_generation_efficiency": "station_generation_efficiency",' + NL +
  '    "station_daily_produced_time": "station_daily_produced_time",',
  "sensor translations")

t = rep(t,
  '        elif unit == "%":' + NL +
  '            self._attr_native_unit_of_measurement = PERCENTAGE' + NL +
  '            self._attr_state_class = SensorStateClass.MEASUREMENT' + NL + NL +
  '    @property' + NL +
  '    def device_info(self):' + NL +
  '        return {' + NL +
  '            "identifiers": {(DOMAIN, self._station_id)},',
  '        elif unit == "%":' + NL +
  '            self._attr_native_unit_of_measurement = PERCENTAGE' + NL +
  '            self._attr_state_class = SensorStateClass.MEASUREMENT' + NL +
  '        elif unit == "kW":' + NL +
  '            self._attr_device_class = SensorDeviceClass.POWER' + NL +
  '            self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT' + NL +
  '            self._attr_state_class = SensorStateClass.MEASUREMENT' + NL +
  '        elif unit == "THB":' + NL +
  '            self._attr_device_class = SensorDeviceClass.MONETARY' + NL +
  '            self._attr_native_unit_of_measurement = unit' + NL +
  '            self._attr_state_class = SensorStateClass.TOTAL' + NL +
  '        elif unit == "h":' + NL +
  '            self._attr_native_unit_of_measurement = UnitOfTime.HOURS' + NL +
  '            self._attr_state_class = SensorStateClass.MEASUREMENT' + NL + NL +
  '    @property' + NL +
  '    def device_info(self):' + NL +
  '        return {' + NL +
  '            "identifiers": {(DOMAIN, self._station_id)},',
  "sensor station unit branches")

t = rep(t,
  '    UnitOfTemperature,' + NL + ')',
  '    UnitOfTemperature,' + NL + '    UnitOfTime,' + NL + ')',
  "sensor import UnitOfTime")
wr(p, t)
print("SENSOR_OK")
