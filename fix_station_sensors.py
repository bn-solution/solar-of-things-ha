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

NL = "\r\n"

# ===== const.py =====
p = "custom_components/solar_of_things/const.py"
t = rd(p)
t = rep(t,
  'API_DEVICE_DETAILS = "/apis/device/details"  # GET ?deviceId=<id>',
  'API_DEVICE_DETAILS = "/apis/device/details"  # GET ?deviceId=<id>' + NL +
  'API_STATION_DETAILS = "/apis/station/details"  # GET ?stationId=<id>',
  "const API_STATION_DETAILS")

t = rep(t,
  '    "daily_production": {' + NL +
  '        "name": "Daily Production",' + NL +
  '        "unit": "kWh",' + NL +
  '        "device_class": "energy",' + NL +
  '        "icon": "mdi:weather-sunny",' + NL +
  '    },',
  '    "daily_production": {' + NL +
  '        "name": "Daily Production",' + NL +
  '        "unit": "kWh",' + NL +
  '        "device_class": "energy",' + NL +
  '        "icon": "mdi:weather-sunny",' + NL +
  '    },' + NL +
  '    # Station-level summary sensors.  Units confirmed by arithmetic cross-checks' + NL +
  '    # from a live station/details capture (2026-09-18, station 517875988254654464):' + NL +
  '    # monthlyProducedQuantity (106.700) = totalGeneratedEnergy (100.678)' + NL +
  '    # + dailyProducedQuantity (6.022); totalEarnings (480.15 THB)' + NL +
  '    # = monthlyProducedQuantity (106.700) x energyIncomePrice (4.50).' + NL +
  '    "station_daily_production": {' + NL +
  '        "name": "Daily Production",' + NL +
  '        "unit": "kWh",' + NL +
  '        "device_class": "energy",' + NL +
  '        "icon": "mdi:calendar-today",' + NL +
  '    },' + NL +
  '    "station_yearly_production": {' + NL +
  '        "name": "Yearly Production",' + NL +
  '        "unit": "kWh",' + NL +
  '        "device_class": "energy",' + NL +
  '        "icon": "mdi:calendar-range",' + NL +
  '    },' + NL +
  '    "station_total_production": {' + NL +
  '        "name": "Total Production",' + NL +
  '        "unit": "kWh",' + NL +
  '        "device_class": "energy",' + NL +
  '        "icon": "mdi:counter",' + NL +
  '    },' + NL +
  '    "station_producing_power": {' + NL +
  '        "name": "Producing Power",' + NL +
  '        "unit": "kW",' + NL +
  '        "device_class": "power",' + NL +
  '        "icon": "mdi:solar-power",' + NL +
  '    },' + NL +
  '    "station_total_earnings": {' + NL +
  '        "name": "Total Earnings",' + NL +
  '        "unit": "THB",' + NL +
  '        "device_class": "monetary",' + NL +
  '        "icon": "mdi:cash",' + NL +
  '    },' + NL +
  '    "station_generation_efficiency": {' + NL +
  '        "name": "Generation Efficiency",' + NL +
  '        "unit": "%",' + NL +
  '        "icon": "mdi:percent-outline",' + NL +
  '    },' + NL +
  '    "station_daily_produced_time": {' + NL +
  '        "name": "Daily Production Time",' + NL +
  '        "unit": "h",' + NL +
  '        "icon": "mdi:clock-outline",' + NL +
  '    },',
  "const station definitions")
wr(p, t)

# ===== api.py =====
p = "custom_components/solar_of_things/api.py"
t = rd(p)
t = rep(t,
  '    API_DEVICE_DETAILS,',
  '    API_DEVICE_DETAILS,' + NL + '    API_STATION_DETAILS,',
  "api import")
t = rep(t,
  '        return data.get("data") or {}' + NL + NL + '    @staticmethod',
  '        return data.get("data") or {}' + NL + NL +
  '    def fetch_station_details(self, station_id: str) -> dict[str, Any]:' + NL +
  '        """Return the raw ``data`` object from the station/details endpoint.' + NL +
  NL +
  '        Source of the station-level summary sensors (daily/yearly/total' + NL +
  '        production, producing power, earnings).  Units confirmed by' + NL +
  '        arithmetic cross-checks from a live capture: monthlyProducedQuantity' + NL +
  '        (106.700) = totalGeneratedEnergy (100.678) + dailyProducedQuantity' + NL +
  '        (6.022); totalEarnings (480.15) = 106.700 x energyIncomePrice (4.50).' + NL +
  '        """' + NL +
  '        self._ensure_token_valid()' + NL +
  '        data = self._get(API_STATION_DETAILS, {"stationId": station_id})' + NL +
  NL +
  '        code = data.get("code")' + NL +
  '        if code not in (0, None, "0"):' + NL +
  '            message = data.get("message") or data.get("msg")' + NL +
  '            raise RuntimeError(f"Station details error code={code} message={message}")' + NL +
  NL +
  '        return data.get("data") or {}' + NL + NL + '    @staticmethod',
  "api fetch_station_details")
wr(p, t)

# ===== __init__.py =====
p = "custom_components/solar_of_things/__init__.py"
t = rd(p)
t = rep(t,
  '            monthly = await self.hass.async_add_executor_job(' + NL +
  '                self.api.fetch_monthly_summary, self.station_id' + NL +
  '            )' + NL +
  '            return {"devices": devices, "monthly": monthly}',
  '            monthly = await self.hass.async_add_executor_job(' + NL +
  '                self.api.fetch_monthly_summary, self.station_id' + NL +
  '            )' + NL +
  '            # Station/details carries authoritative production totals whose' + NL +
  '            # units are confirmed by arithmetic cross-checks (see' + NL +
  '            # SolarOfThingsAPI.fetch_station_details).  The generic monthly' + NL +
  '            # summary endpoint returns 0 for station-firmware combos whose' + NL +
  '            # summary keys differ, so the confirmed station figures win.' + NL +
  '            # Additive: a failure here must not take the station update' + NL +
  '            # down; TokenExpiredError still triggers re-auth.' + NL +
  '            try:' + NL +
  '                details = await self.hass.async_add_executor_job(' + NL +
  '                    self.api.fetch_station_details, self.station_id' + NL +
  '                )' + NL +
  '            except TokenExpiredError:' + NL +
  '                raise' + NL +
  '            except Exception as err:' + NL +
  '                _LOGGER.debug(' + NL +
  '                    "SolarOfThings station %s: station details unavailable: %s",' + NL +
  '                    self.station_id, err,' + NL +
  '                )' + NL +
  '                details = None' + NL +
  '            if details:' + NL +
  '                mpq = details.get("monthlyProducedQuantity")' + NL +
  '                if mpq is not None:' + NL +
  '                    monthly["monthly_pv_generated"] = float(mpq)' + NL +
  '                station_fields = (' + NL +
  '                    ("station_daily_production", "dailyProducedQuantity"),' + NL +
  '                    ("station_yearly_production", "yearlyProducedQuantity"),' + NL +
  '                    ("station_total_production", "totalProducedQuantity"),' + NL +
  '                    ("station_producing_power", "producingPower"),' + NL +
  '                    ("station_total_earnings", "totalEarnings"),' + NL +
  '                    ("station_generation_efficiency", "generationEfficiency"),' + NL +
  '                    ("station_daily_produced_time", "dailyProducedTime"),' + NL +
  '                )' + NL +
  '                for key, field in station_fields:' + NL +
  '                    v = details.get(field)' + NL +
  '                    if v is not None:' + NL +
  '                        monthly[key] = float(v)' + NL +
  '            return {"devices": devices, "monthly": monthly}',
  "init station merge")
wr(p, t)

# ===== sensor.py =====
p = "custom_components/solar_of_things/sensor.py"
t = rd(p)

# per-device loop: ห้ามสร้าง station_* เป็น per-device
t = rep(t,
  '            if key.startswith("monthly_"):' + NL + '                continue',
  '            if key.startswith("monthly_") or key.startswith("station_"):' + NL + '                continue',
  "sensor per-device loop")

# station loop: เพิ่ม station_*
t = rep(t,
  '            if not key.startswith("monthly_"):' + NL + '                continue',
  '            if not (key.startswith("monthly_") or key.startswith("station_")):' + NL + '                continue',
  "sensor station loop")

# translations
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

# StationMonthlySensor unit branches: kW, THB, h (เพิ่มหลัง branch %)
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

# import UnitOfTime
t = rep(t,
  '    UnitOfPower,' + NL + ')',
  '    UnitOfPower,' + NL + '    UnitOfTime,' + NL + ')',
  "sensor import UnitOfTime")
wr(p, t)

# ===== strings.json + en.json =====
for p in ["custom_components/solar_of_things/strings.json",
          "custom_components/solar_of_things/translations/en.json"]:
    t = rd(p)
    t = rep(t,
      '      "ntc_maximum_temperature": {' + NL + '        "name": "NTC Maximum Temperature"' + NL + '      },',
      '      "ntc_maximum_temperature": {' + NL + '        "name": "NTC Maximum Temperature"' + NL + '      },' + NL +
      '      "station_daily_production": {' + NL + '        "name": "Daily Production"' + NL + '      },' + NL +
      '      "station_yearly_production": {' + NL + '        "name": "Yearly Production"' + NL + '      },' + NL +
      '      "station_total_production": {' + NL + '        "name": "Total Production"' + NL + '      },' + NL +
      '      "station_producing_power": {' + NL + '        "name": "Producing Power"' + NL + '      },' + NL +
      '      "station_total_earnings": {' + NL + '        "name": "Total Earnings"' + NL + '      },' + NL +
      '      "station_generation_efficiency": {' + NL + '        "name": "Generation Efficiency"' + NL + '      },' + NL +
      '      "station_daily_produced_time": {' + NL + '        "name": "Daily Production Time"' + NL + '      },',
      p)
    wr(p, t)

print("STATION_OK")
