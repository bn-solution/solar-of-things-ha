"""Constants for the Solar of Things integration."""

DOMAIN = "solar_of_things"

# ─── Configuration keys ────────────────────────────────────────────────────────
CONF_IOT_TOKEN = "iot_token"          # legacy / advanced manual entry
CONF_STATION_ID = "station_id"
CONF_DEVICE_ID = "device_id"
CONF_TIME_ZONE = "time_zone"

# Credential-based auth (preferred)
CONF_USER_ID = "user_id"       # Siseli account / user-ID login (not email)
CONF_PASSWORD = "password"

# Fields that are typed or copy-pasted by hand and routinely arrive with stray
# leading/trailing whitespace.  The upstream API treats " 4235…" as a different
# (invalid) value, which surfaces to the user as an unhelpful "cannot connect".
# Consumed by normalise_config_fields() in util.py, which is applied both when
# the config flow accepts input and when an entry is read back at setup, so a
# single list keeps the two paths from drifting.
# CONF_PASSWORD is deliberately absent: whitespace in a password may be
# significant, so it is never trimmed.
WHITESPACE_SENSITIVE_FIELDS = (
    CONF_USER_ID,
    CONF_STATION_ID,
    CONF_DEVICE_ID,
    CONF_IOT_TOKEN,
    CONF_TIME_ZONE,
)

# Runtime-stored token state (written back to config entry)
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN_EXPIRES = "access_token_expires"   # ISO-8601 string
CONF_REFRESH_TOKEN_EXPIRES = "refresh_token_expires" # ISO-8601 string

# ─── API bases ─────────────────────────────────────────────────────────────────
# Both auth and data endpoints live on the production server solar.siseli.com.
# The portal JS bundle embeds both test/prod AppIDs; AppID rBrTRfAPXz is the
# one accepted by solar.siseli.com (confirmed by live API testing 2026-03-07).
API_BASE_URL        = "https://solar.siseli.com"         # data endpoints
API_AUTH_BASE_URL   = "https://solar.siseli.com"         # auth / login endpoints

# ─── Auth endpoints (discovered from portal JS bundle) ─────────────────────────
# The login endpoint requires IOT-Open-AppID signing (see api.py _sign_request).
API_LOGIN           = "/apis/login/account"              # POST + signed headers
API_REFRESH_TOKEN   = "/apis/login/refresh/access/token"  # POST, no token needed

# ─── IOT Open Platform app credentials (embedded in portal umi.js) ────────────
# rBrTRfAPXz is the production AppID accepted by solar.siseli.com.
# JO4DAiNeys is the test AppID (accepted only by test.solar.siseli.com).
IOT_APP_ID          = "rBrTRfAPXz"
IOT_APP_SECRET_ENC  = "I4D0KRr2339z3pQ/at91V9BpFAOe54DaTafwSm6suIQ="

# ─── Data endpoints ────────────────────────────────────────────────────────────
API_TIME_SERIES    = "/apis/deviceState/simple/attribute/keys/history/v1"
API_MONTHLY_SUMMARY = "/apis/stationOverView/stateAttributeSummary/category/yearly"
# Remote device config endpoints (discovered 2026-03-07 from live API testing).
# These accept a plain IOT-Token header (no IOT-Open-Sign) and use the device ID
# as a query parameter.  Write sends one setting key+value per call.
API_SETTINGS_GET   = "/apis/remote/device/configs/cache/get"  # ?deviceId=<id>
API_SETTINGS_SET   = "/apis/remote/device/config/write"       # ?deviceId=<id>
API_DEVICE_LIST    = "/apis/device/list"
API_DEVICE_DETAILS = "/apis/device/details"  # GET ?deviceId=<id>
API_STATION_DETAILS = "/apis/station/details"  # GET ?stationId=<id>
# Live "energy flow" endpoint.  GET with ?deviceId=<id>&dataSource=1; values are
# returned under data.deviceAttributeState.fields.  Used as a fallback when the
# historical time-series endpoint yields nothing (see ENERGY_FLOW_RULES below).
API_ENERGY_FLOW    = "/apis/deviceState/simple/energy/flow/v1"
# Device "latest state" endpoint (dataSource=2).  GET ?deviceId=<id>&dataSource=2
# returns data.fields as a map of {fieldKey: {unit, value, valueDisplay,
# nameDisplay}} covering every attribute the firmware reports — including the
# enum states (workingStates, gridState, batState, ...) that the historical
# time-series endpoint never carries.
API_LATEST_STATE   = "/apis/deviceState/simple/state/latest/v1"

# ─── Token refresh window ──────────────────────────────────────────────────────
# Refresh the access token this many seconds *before* its stated expiry.
# Mirrors the portal JS which refreshes when ≤300 s remain.
TOKEN_REFRESH_LEAD_SECONDS = 300  # 5 minutes

# ─── Sensor keys ───────────────────────────────────────────────────────────────
SENSOR_KEYS = [
    "pvInputPower",
    "pvInputVoltage",
    "acOutputActivePower",
    "acInputVoltage",
    "acInputFrequency",
    "outputVoltage",
    "outputFrequency",
    "outputApparentPower",
    "loadPercentage",
    "batteryDischargeCurrent",
    "batteryChargingCurrent",
    "batteryVoltage",
    "feedInPower",
    "batteryPower",
    "batterySOC",
    "gridPower",
    "loadPower",
    "ntcMaximumTemperature",
]

# ─── Energy-flow fallback mapping ──────────────────────────────────────────────
# Several inverter / WiFi-dongle firmware families never populate the historical
# time-series endpoint (API_TIME_SERIES) that this integration reads by default,
# so every realtime sensor stays "unknown" while the portal shows live data.
# Reported for UWB1, RWB1-0x, JC-62xx, DatouBoss DT-series and EASUN units in
# https://github.com/Conexo-Casa/solar-of-things-ha/issues/7 (and #3, #8, #11,
# #14, #15).  Those devices serve live values from API_ENERGY_FLOW instead,
# under a different set of field names.
#
# Each canonical sensor key maps to an ordered list of rules.  The first rule
# that produces a usable number wins.  A rule is (mode, source_fields, scale):
#   "first" – use the first source field that is present
#   "sum"   – add every source field that is present (multi-string PV inputs)
# `scale` converts the source value into the unit declared in
# SENSOR_DEFINITIONS.
#
# ONLY mappings whose unit AND (where relevant) sign are confirmed by an
# observed value are enabled here — no rule in this table can be 1000x wrong
# or have charge/discharge backwards. Two capture rounds confirmed the table
# below:
#   Night (0 W, settles nothing but the always-zero fields):
#     bmsBatteryVoltage / positiveTerminalBatteryVoltage   26.6 V
#     batteryPercentage / bmsSOC                           100 %
#     batteryPower                                         9 W
#     pv1Power / pv2Power                                  W (labelled; 0 at night)
#   Daylight, four states — AC/no-AC x charging/discharging (issue #7,
#   2026-09-15, hidemichixt-creator's four-file capture set) — settled the
#   rest via the API's own per-field "unit" tag plus arithmetic cross-checks:
#     load_power              "unit": "kW" in the payload itself (not guessed).
#                              AC Output Power / Load Power.
#     aPhaseMainsPower/b/c     "unit": "W" in the payload itself. Sign confirmed
#                              by conservation of power: load_power + charging
#                              batteryPower − pv1Power reproduces
#                              |aPhaseMainsPower| to within rounding in both
#                              AC-connected samples (e.g. 614+720−234=1100 W).
#                              Negative = importing from mains, positive =
#                              feeding in — confirmed directly (not just by
#                              symmetry) by a follow-up capture with the
#                              battery full and PV surplus flowing out
#                              (897 W PV, 0 W battery, 351 W load ->
#                              +495 W on aPhaseMainsPower, the ~50 W gap
#                              being ordinary inverter conversion loss).
#     positiveTerminalBatteryCurrent   Sign flips consistently across all four
#                              states: negative while charging (-17.6, -27 A),
#                              positive while discharging (+25.5, +17.6 A).
#                              negativeTerminalBatteryCurrent stayed 0 in every
#                              sample on this device/firmware and is still
#                              unused — see ENERGY_FLOW_UNVERIFIED.
# Rule modes: "first" (first present source wins), "sum" (add every present
# source), "clamp_pos" (sum, then max(0, total) — the positive/export half of
# a signed field), "clamp_neg" (sum, then max(0, -total) — the negative/import
# half). `scale` converts the source value into the unit declared in
# SENSOR_DEFINITIONS.
ENERGY_FLOW_RULES: dict[str, list[tuple[str, tuple[str, ...], float]]] = {
    "pvInputPower": [
        ("sum", ("pv1Power", "pv2Power", "pv3Power", "pv4Power"), 1.0),
    ],
    # Confirmed by a live capture (per-field "unit": "V", device 517915003814383616).
    "pvInputVoltage": [
        ("first", ("pvInputVoltage",), 1.0),
    ],
    "batteryVoltage": [
        ("first", ("bmsBatteryVoltage", "positiveTerminalBatteryVoltage"), 1.0),
    ],
    "batterySOC": [
        ("first", ("batteryPercentage", "bmsSOC", "batteryCapacity"), 1.0),
    ],
    "batteryPower": [
        ("first", ("batteryPower",), 1.0),
    ],
    "acOutputActivePower": [
        ("sum", ("load_power",), 1000.0),
    ],
    # Confirmed by a live capture (per-field "unit": "V", device 517915003814383616).
    "acInputVoltage": [
        ("first", ("acInputVoltage",), 1.0),
    ],
    # Confirmed by a live capture (per-field "unit": "V", device 517915003814383616).
    "outputVoltage": [
        ("first", ("outputVoltage",), 1.0),
    ],
    # Confirmed by a live capture (per-field "unit" tags, device 517915003814383616).
    "acInputFrequency": [
        ("first", ("acInputFrequency",), 1.0),
    ],
    "outputFrequency": [
        ("first", ("outputFrequency",), 1.0),
    ],
    "outputApparentPower": [
        ("first", ("outputApparentPower",), 1.0),
    ],
    "loadPercentage": [
        ("first", ("loadPercentage",), 1.0),
    ],
    "ntcMaximumTemperature": [
        ("first", ("ntcMaximumTemperature",), 1.0),
    ],
    "gridPower": [
        ("clamp_neg", ("aPhaseMainsPower", "bPhaseMainsPower", "cPhaseMainsPower"), 1.0),
    ],
    "feedInPower": [
        ("clamp_pos", ("aPhaseMainsPower", "bPhaseMainsPower", "cPhaseMainsPower"), 1.0),
    ],
    "batteryChargingCurrent": [
        ("clamp_neg", ("positiveTerminalBatteryCurrent",), 1.0),
    ],
    "batteryDischargeCurrent": [
        ("clamp_pos", ("positiveTerminalBatteryCurrent",), 1.0),
    ],
}

# Fields observed in issue #7 payloads that are still deliberately NOT mapped.
# Publishing a wrong value is worse than leaving a sensor "unknown": a 1000x
# scaling error feeds the HA Energy dashboard and long-term statistics, and
# statistics cannot be un-poisoned by a later fix.
ENERGY_FLOW_UNVERIFIED: tuple[str, ...] = (
    "generationPower",    # kW aggregate matching pv1Power+pv2Power exactly on
                           # every sample so far, but redundant with the
                           # per-string sum above — no reason to add a second,
                           # less precise path for the same number.
    "loadPower",           # camelCase alternate of the confirmed load_power
                           # key; no capture has shown a device that reports
                           # this spelling instead, so its unit is unconfirmed.
    "negativeTerminalBatteryCurrent",  # stayed 0 in every capture on this
                           # device/firmware; positiveTerminalBatteryCurrent's
                           # sign already covers both directions, so this
                           # field has no confirmed use yet.
)

# Canonical keys that indicate the time-series endpoint returned usable realtime
# data.  If none of these are present the energy-flow fallback is attempted.
REALTIME_PROBE_KEYS: tuple[str, ...] = (
    "pvInputPower",
    "acOutputActivePower",
    "batteryVoltage",
    "batterySOC",
    "batteryChargingCurrent",
    "batteryDischargeCurrent",
    "feedInPower",
)

SENSOR_DEFINITIONS = {
    "pvInputPower": {
        "name": "PV Input Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:solar-power",
    },
    "pvInputVoltage": {
        "name": "PV Input Voltage",
        "unit": "V",
        "device_class": "voltage",
        "icon": "mdi:solar-power",
    },
    "acOutputActivePower": {
        "name": "AC Output Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:power-plug",
        # The latest-state endpoint reports this field in kW; the latest-state
        # fallback in sensor.py scales it into the declared W unit.
        "latest_scale": 1000.0,
    },
    "acInputVoltage": {
        "name": "AC Input Voltage",
        "unit": "V",
        "device_class": "voltage",
        "icon": "mdi:transmission-tower",
    },
    "outputVoltage": {
        "name": "Output Voltage",
        "unit": "V",
        "device_class": "voltage",
        "icon": "mdi:power-plug",
    },
    "acInputFrequency": {
        "name": "AC Input Frequency",
        "unit": "Hz",
        "device_class": "frequency",
        "icon": "mdi:sine-wave",
    },
    "outputFrequency": {
        "name": "Output Frequency",
        "unit": "Hz",
        "device_class": "frequency",
        "icon": "mdi:sine-wave",
    },
    "outputApparentPower": {
        "name": "Output Apparent Power",
        "unit": "VA",
        "device_class": "apparent_power",
        "icon": "mdi:flash",
    },
    "loadPercentage": {
        "name": "Load Percentage",
        "unit": "%",
        "icon": "mdi:gauge",
    },
    "ntcMaximumTemperature": {
        "name": "NTC Maximum Temperature",
        "unit": "℃",
        "device_class": "temperature",
        "icon": "mdi:thermometer",
    },
    "batteryDischargeCurrent": {
        "name": "Battery Discharge Current",
        "unit": "A",
        "device_class": "current",
        "icon": "mdi:battery-arrow-down",
    },
    "batteryChargingCurrent": {
        "name": "Battery Charging Current",
        "unit": "A",
        "device_class": "current",
        "icon": "mdi:battery-arrow-up",
    },
    "batteryVoltage": {
        "name": "Battery Voltage",
        "unit": "V",
        "device_class": "voltage",
        "icon": "mdi:battery",
    },
    "batteryPower": {
        "name": "Battery Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:battery-charging",
    },
    "batterySOC": {
        "name": "Battery State of Charge",
        "unit": "%",
        "device_class": "battery",
        "icon": "mdi:battery",
    },
    "feedInPower": {
        "name": "Grid Feed-in Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:transmission-tower-export",
    },
    "gridPower": {
        "name": "Grid Import Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:transmission-tower-import",
    },
    "loadPower": {
        "name": "Load Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:home-lightning-bolt",
    },
    # ─── Latest-state attributes (deviceState/simple/state/latest, dataSource=2)
    # Every field the firmware reports, from a live capture (2026-10-06,
    # device 517915003814383616).  Units are the API's own per-field "unit"
    # tags.  Fields without a unit are enums/text and render valueDisplay
    # ("Line Mode", "CSO", ...) as a string state.  kW sources scale into W
    # via "latest_scale" (applied by the latest-state fallback in sensor.py).
    "workingStates": {
        "name": "Working State",
        "icon": "mdi:state-machine",
    },
    "gridState": {"name": "Grid State", "icon": "mdi:transmission-tower"},
    "batState": {"name": "Battery State", "icon": "mdi:battery"},
    "loadStatus": {"name": "Load Status", "icon": "mdi:home-lightning-bolt"},
    "outputRelayStatus": {"name": "Output Relay Status", "icon": "mdi:electric-switch"},
    "mainsRelayStatus": {"name": "Mains Relay Status", "icon": "mdi:electric-switch"},
    "photovoltaicAccessFlag": {"name": "PV Access Flag", "icon": "mdi:solar-power"},
    "pvStatuss": {"name": "PV Status", "icon": "mdi:solar-power"},
    "outputSourcePriority": {"name": "Output Source Priority", "icon": "mdi:swap-horizontal"},
    "chargerSourcePriority": {"name": "Charger Source Priority", "icon": "mdi:battery-charging"},
    "batteryType": {"name": "Battery Type", "icon": "mdi:battery"},
    "mainsInputRange": {"name": "Mains Input Range", "icon": "mdi:transmission-tower"},
    "batteryEqualizationMode": {"name": "Battery Equalization", "icon": "mdi:battery-sync"},
    "startBalancing": {"name": "Start Balancing Immediately", "icon": "mdi:battery-sync"},
    "dualOutputVoltageSwitch": {"name": "Dual Output Switch", "icon": "mdi:electric-switch"},
    "gridConnectedSwitch1": {"name": "Grid Connected Switch", "icon": "mdi:electric-switch"},
    "ledPatternLight1": {"name": "LED Pattern Switch", "icon": "mdi:led-on"},
    "mainsAccessDelayEnabled": {"name": "Mains Access Delay", "icon": "mdi:timer"},
    "mainCPUVersion1": {"name": "Main CPU Version", "icon": "mdi:chip"},
    "generationPower": {
        "name": "Generation Power",
        "unit": "W",
        "device_class": "power",
        "icon": "mdi:solar-power",
        "latest_scale": 1000.0,
    },
    "ratedActivePower": {"name": "Nominal Active Power", "unit": "W", "device_class": "power", "icon": "mdi:power-plug"},
    "acOutputRatingApparentPower": {"name": "Nominal Apparent Power", "unit": "VA", "device_class": "apparent_power", "icon": "mdi:flash"},
    "ratingOutputCurrent": {"name": "Nominal Output Current", "unit": "A", "device_class": "current", "icon": "mdi:current-ac"},
    "nominalAcCurrent": {"name": "Nominal AC Current", "unit": "A", "device_class": "current", "icon": "mdi:current-ac"},
    "gridConnectedCurrent": {"name": "Grid Connected Current Set", "unit": "A", "device_class": "current", "icon": "mdi:transmission-tower"},
    "maxTotalChargeCurrent": {"name": "Max Total Charge Current", "unit": "A", "device_class": "current", "icon": "mdi:battery-charging"},
    "maxUtilityChargeCurrent1": {"name": "Utility Charge Current", "unit": "A", "device_class": "current", "icon": "mdi:transmission-tower"},
    "bmsBatteryDischargeCurrent": {"name": "BMS Battery Discharge Current", "unit": "A", "device_class": "current", "icon": "mdi:battery-arrow-down"},
    "bmsBatteryChargingCurrent": {"name": "BMS Battery Charging Current", "unit": "A", "device_class": "current", "icon": "mdi:battery-arrow-up"},
    "lowBatteryCutOffVoltage": {"name": "Low Battery Cut-off Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-minus"},
    "ratedBatteryVoltage": {"name": "Nominal Battery Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery"},
    "bmsBatteryVoltage": {"name": "BMS Battery Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery"},
    "bmsSingleSectionMinimumVoltage": {"name": "BMS Cell Minimum Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-outline"},
    "maximumVoltageBmsSingleSection": {"name": "BMS Cell Maximum Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-outline"},
    "dualOutputTurnOffVoltage": {"name": "Dual Output Cut-off Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-minus"},
    "comebackUtilityModeVolSBUPriorityStatus": {"name": "SBU Back To Utility Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:transmission-tower"},
    "comebackBatteryModeVolSBUPriorityStatus": {"name": "SBU Back To Battery Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery"},
    "floatChargingVoltage": {"name": "Float Charging Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-charging"},
    "bulkChargingVoltage": {"name": "Bulk Charging Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-charging"},
    "batteryEqualizationVoltage": {"name": "Battery Equalization Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery-sync"},
    "nominalAcVoltage": {"name": "Nominal AC Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:transmission-tower"},
    "ratedOutputVoltage": {"name": "Nominal Output Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:power-plug"},
    # batteryRatingVoltage: the firmware itself reports 230 V under
    # "rated voltage" for the battery while ratedBatteryVoltage says 48 V —
    # a firmware mislabel.  Published as-is (it is what the device reports);
    # drop it if it proves noisy.
    "batteryRatingVoltage": {"name": "Battery Rated Voltage", "unit": "V", "device_class": "voltage", "icon": "mdi:battery"},
    "ratedOutputFrequency": {"name": "Nominal Output Frequency", "unit": "Hz", "device_class": "frequency", "icon": "mdi:sine-wave"},
    "batteryCapacity": {"name": "Battery Capacity", "unit": "%", "icon": "mdi:battery"},
    "bmsBatterySOC": {"name": "BMS Battery SOC", "unit": "%", "icon": "mdi:battery"},
    "dualOutputTurnsOffTheSOC": {"name": "Dual Output Cut-off SOC", "unit": "%", "icon": "mdi:battery-arrow-down"},
    "dualOutputLimitPowerPercentage": {"name": "Dual Output Limit Power Percentage", "unit": "%", "icon": "mdi:gauge"},
    "backToUtility": {"name": "Back To Utility SOC", "unit": "%", "icon": "mdi:transmission-tower"},
    "batteryVoltUnderTurnOffSOC": {"name": "Battery Volt Under Cut-off SOC", "unit": "%", "icon": "mdi:percent"},
    "batVoltBackToBat": {"name": "Battery Volt Back To Battery SOC", "unit": "%", "icon": "mdi:percent"},
    "maximumTemperatureBmsSingleSection": {"name": "BMS Cell Maximum Temperature", "unit": "℃", "device_class": "temperature", "icon": "mdi:thermometer"},
    "bmsSingleSectionMinimumTemperature": {"name": "BMS Cell Minimum Temperature", "unit": "℃", "device_class": "temperature", "icon": "mdi:thermometer"},
    "bmsMosTemperature": {"name": "BMS MOS Temperature", "unit": "℃", "device_class": "temperature", "icon": "mdi:thermometer"},
    "bmsAmbientTemperature": {"name": "BMS Ambient Temperature", "unit": "℃", "device_class": "temperature", "icon": "mdi:thermometer"},
    "numberOfBMSCycles": {"name": "BMS Cycle Count", "icon": "mdi:counter"},
    "bmsBatteryCapacity": {"name": "BMS Battery Capacity", "unit": "Ah", "icon": "mdi:battery"},
    "batteryEqualizationInterval": {"name": "Battery Equalization Interval", "unit": "day", "icon": "mdi:calendar-clock"},
    "batteryEqualizationTime": {"name": "Battery Equalization Time", "unit": "min", "icon": "mdi:clock-outline"},
    "batteryEqualizationTimeout": {"name": "Battery Equalization Timeout", "unit": "min", "icon": "mdi:clock-outline"},
    # batteryNumber ("Battery Piece") is deliberately NOT mapped: the same
    # field carries value=2, valueDisplay="48" and unit "V" — three mutually
    # inconsistent readings.  A wrong number is worse than an absent sensor.

    # Monthly summary sensors
    "monthly_pv_generated": {
        "name": "Monthly PV Generated",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:solar-power",
    },
    "monthly_grid_import": {
        "name": "Monthly Grid Import",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:transmission-tower-import",
    },
    "monthly_total_consumption": {
        "name": "Monthly Total Consumption",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:home-lightning-bolt",
    },
    "monthly_solar_percentage": {
        "name": "Monthly Solar Coverage",
        "unit": "%",
        "icon": "mdi:percent",
    },
    # Daily production (per-device, from device/details).
    # Unit kWh confirmed by arithmetic cross-check from a live capture
    # (2026-09-18, device 517915003814383616):
    #   totalProducedQuantity (99.468) = totalGeneratedEnergy (97.939)
    #                                  + dailyProducedQuantity (1.529)
    # dailyProducedQuantity resets every day.
    "daily_production": {
        "name": "Daily Production",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:weather-sunny",
    },
    # Station-level summary sensors.  Units confirmed by arithmetic cross-checks
    # from a live station/details capture (2026-09-18, station 517875988254654464):
    # monthlyProducedQuantity (106.700) = totalGeneratedEnergy (100.678)
    # + dailyProducedQuantity (6.022); totalEarnings (480.15 THB)
    # = monthlyProducedQuantity (106.700) x energyIncomePrice (4.50).
    "station_daily_production": {
        "name": "Daily Production",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:calendar-today",
    },
    "station_yearly_production": {
        "name": "Yearly Production",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:calendar-range",
    },
    "station_total_production": {
        "name": "Total Production",
        "unit": "kWh",
        "device_class": "energy",
        "icon": "mdi:counter",
    },
    "station_producing_power": {
        "name": "Producing Power",
        "unit": "kW",
        "device_class": "power",
        "icon": "mdi:solar-power",
    },
    "station_total_earnings": {
        "name": "Total Earnings",
        "unit": "THB",
        "device_class": "monetary",
        "icon": "mdi:cash",
    },
    # Total Earnings Per Month = monthly production (kWh) x tariff (THB/kWh),
    # computed in the station coordinator.  Cross-checked against a live
    # capture: 480.15 = 106.700 x 4.50.
    "station_monthly_earnings": {
        "name": "Total Earnings Per Month",
        "unit": "THB",
        "device_class": "monetary",
        "icon": "mdi:cash-multiple",
    },
    "station_generation_efficiency": {
        "name": "Generation Efficiency",
        "unit": "%",
        "icon": "mdi:percent-outline",
    },
    "station_daily_produced_time": {
        "name": "Daily Production Time",
        "unit": "h",
        "icon": "mdi:clock-outline",
    },
}

# ─── Device-setting key aliases (write path) ───────────────────────────────────
# Several inverter firmwares expose the same logical control under a different
# writable-config key name than the one this integration was written against —
# the same class of bug #13 already fixed for sensor *reads*, but here for
# control *writes* (and their matching read-back for current state). Confirmed
# by lukaszkwapien's full writable-config dump for a FCHAO inverter (#18):
#   Output Source Priority: the documented `outputSourcePrioritySetting` fails
#   with `code=70134 "Config attribute not exists"` on this firmware, which
#   exposes the same control as `setOutputSourcePriority` instead.
# Every other control below has no confirmed alternate name yet — its tuple is
# just itself. The same dump also confirmed FCHAO does not expose
# batteryChargeLimit / batteryDischargeLimit / gridChargeLimit under ANY name;
# for those, resolve_setting_key() in api.py returning None is used to mark
# the entity unavailable rather than let the user trigger a write that is
# guaranteed to fail with the same portal error.
SETTING_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "outputSourcePrioritySetting": ("outputSourcePrioritySetting", "setOutputSourcePriority"),
    "chargerSourcePrioritySetting": ("chargerSourcePrioritySetting",),
    "acInputRangeSetting": ("acInputRangeSetting",),
    "batteryPowerLimitingSetting": ("batteryPowerLimitingSetting",),
    "batteryChargeLimit": ("batteryChargeLimit",),
    "batteryDischargeLimit": ("batteryDischargeLimit",),
    "gridChargeLimit": ("gridChargeLimit",),
}
