import json
import logging
import time
import asyncio
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode, PRESET_NONE
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

logger = logging.getLogger(__name__)

PRESET_PRIORITY = "Priority"
PRESET_NORMAL = PRESET_NONE

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up MyPlaceIQ climate entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    myplaceiq = hass.data[DOMAIN][entry.entry_id]["myplaceiq"]
    data = coordinator.data

    if not isinstance(data, dict) or not data or "body" not in data:
        logger.error("Invalid or missing coordinator data: %s", data)
        return

    try:
        body = json.loads(data["body"])
    except (json.JSONDecodeError, TypeError) as err:
        logger.error("Failed to parse coordinator data body: %s", err)
        return

    aircons = body.get("aircons", {})
    zones = body.get("zones", {})

    entities = []

    # System climate entity
    for aircon_id, aircon_data in aircons.items():
        entities.append(
            MyPlaceIQClimate(
                coordinator=coordinator,
                myplaceiq=myplaceiq,
                config_entry=entry,
                entity_id=aircon_id,
                entity_data=aircon_data,
                is_zone=False
            )
        )
    # Zone climate entities
    for aircon_id, aircon_data in aircons.items():
        for zone_id in aircon_data.get("zoneOrder", []):
            zone_data = zones.get(zone_id)
            if zone_data and zone_data.get("isVisible", False):
                entities.append(
                    MyPlaceIQClimate(
                        coordinator=coordinator,
                        myplaceiq=myplaceiq,
                        config_entry=entry,
                        entity_id=zone_id,
                        entity_data=zone_data,
                        is_zone=True,
                        aircon_id=aircon_id
                    )
                )

    if entities:
        async_add_entities(entities)
        logger.debug("Added %d climate entities", len(entities))
    else:
        logger.warning("No climate entities created; check data structure")

class MyPlaceIQClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    def __init__(
        self,
        coordinator,
        myplaceiq,
        config_entry,
        entity_id,
        entity_data,
        is_zone,
        aircon_id=None
    ):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._myplaceiq = myplaceiq
        self._config_entry = config_entry
        self._entity_id = entity_id
        self._is_zone = is_zone
        self._aircon_id = aircon_id if is_zone else entity_id
        self._name = entity_data.get("name", "Zone" if is_zone else "Aircon")
        self._attr_unique_id = f"{config_entry.entry_id}_{'zone' if is_zone else 'aircon'}_{entity_id}_climate"
        self._attr_name = f"{self._name}_climate".replace(" ", "_").lower()
        self._attr_icon = "mdi:thermostat"
        self._attr_hvac_modes = (
            [HVACMode.AUTO, HVACMode.OFF] if is_zone else
            [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]
        )
        
        if is_zone:
            if entity_data.get("isPriorityZoneAllowed", False):
                self._attr_supported_features = (
                    ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
                )
                self._attr_preset_modes = [PRESET_PRIORITY, PRESET_NORMAL]
            else:
                self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
                self._attr_preset_modes = None
        else:
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
            )
            self._attr_preset_modes = None

        self._last_known_is_on = None

    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        logger.debug("Coordinator update for %s at %s", self._attr_unique_id, time.strftime("%H:%M:%S"))
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, f"{self._config_entry.entry_id}_{'zone' if self._is_zone else 'aircon'}_{self._entity_id}")},
            "name": f"{'Zone' if self._is_zone else 'Aircon'} {self._name}",
            "manufacturer": "MyPlaceIQ",
            "model": "Zone" if self._is_zone else "Aircon"
        }
        if self._is_zone:
            device_info["via_device"] = (DOMAIN, f"{self._config_entry.entry_id}_aircon_{self._aircon_id}")
        return device_info

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def current_temperature(self):
        """Return the current temperature."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None
        try:
            body = json.loads(data["body"])
            target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
            return target.get("temperatureSensorValue" if self._is_zone else "actualTemperature")
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse current temperature: %s", err)
            return None

    @property
    def target_temperature(self):
        """Return the target temperature based on the aircon's mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return None
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
            mode = aircon.get("mode", "heat")
            target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
            if mode == "heat":
                val = target.get("targetTemperatureHeat")
            elif mode == "cool":
                val = target.get("targetTemperatureCool")
            else:
                val = None
            return float(val) if val is not None else None
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse target temperature: %s", err)
            return None

    @property
    def fan_modes(self) -> list[str] | None:
        """Return the list of available fan modes standardized for Home Assistant cards."""
        if self._is_zone:
            return None
        return ["low", "medium", "high", "auto"]
    
    @property
    def fan_mode(self) -> str | None:
        """Return current fan setting evaluated dynamically from active HVAC registers."""
        if self._is_zone:
            return None
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return "low"
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id, {})
            
            if aircon.get("isMyAutoEnabled") is True:
                return "auto"
            
            mode = aircon.get("mode", "cool")
            # Routing path splits: heat mode uses Heat fields, cool/fan/dry modes use Cool fields
            if mode == "heat":
                if aircon.get("isMyFanHeatingEnabled") is True:
                    return "auto"
                speed = aircon.get("fanSpeedHeat", 1)
            else:
                if aircon.get("isMyFanCoolingEnabled") is True:
                    return "auto"
                speed = aircon.get("fanSpeedCool", 1)

            if speed == 1:
                return "low"
            elif speed == 2:
                return "medium"
            elif speed == 3:
                return "high"
        except (json.JSONDecodeError, TypeError):
            pass
        return "low"
        
    @property
    def hvac_mode(self):
        """Return the current HVAC mode."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            logger.debug("No valid coordinator data for %s", self._attr_unique_id)
            return HVACMode.OFF
        try:
            body = json.loads(data["body"])
            aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
            is_on = aircon.get("isOn", self._last_known_is_on if self._last_known_is_on is not None else False)
            if is_on:
                self._last_known_is_on = is_on
            if self._is_zone:
                zone = body.get("zones", {}).get(self._entity_id, {})
                is_zone_on = zone.get("isOn", False)
                if is_zone_on:
                    self._last_known_is_on = is_zone_on
                state = HVACMode.OFF if not is_zone_on else HVACMode.AUTO
                logger.debug("Zone %s hvac_mode updated: %s", self._attr_unique_id, state)
                return state
            state = (
                HVACMode.OFF if not is_on else
                HVACMode.HEAT if aircon.get("mode") == "heat" else
                HVACMode.COOL if aircon.get("mode") == "cool" else
                HVACMode.DRY if aircon.get("mode") == "dry" else
                HVACMode.FAN_ONLY if aircon.get("mode") == "fan" else
                HVACMode.OFF
            )
            return state
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse HVAC mode: %s", err)
            return HVACMode.OFF

    @property
    def preset_mode(self):
        """Return the current preset mode for zone entities."""
        if not self._is_zone or self._attr_preset_modes is None:
            return None
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return PRESET_NORMAL
        try:
            body = json.loads(data["body"])
            zone = body.get("zones", {}).get(self._entity_id, {})
            is_priority = zone.get("isPriorityZone", False)
            return PRESET_PRIORITY if is_priority else PRESET_NORMAL
        except (json.JSONDecodeError, TypeError) as err:
            logger.error("Failed to parse preset mode: %s", err)
            return PRESET_NORMAL

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature using verified working Command Array format."""
        temperature = kwargs.get("temperature")
        if temperature is None:
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])
        aircon = body.get("aircons", {}).get(self._aircon_id if self._is_zone else self._entity_id, {})
        mode = aircon.get("mode", "heat")
        target_temp = float((round(temperature * 2))/2.0)

        command = {
            "commands": [{
                "__type": (
                    "SetZoneHeatTemperature" if mode == "heat" else "SetZoneCoolTemperature"
                ) if self._is_zone else (
                    "SetAirconHeatTemperature" if mode == "heat" else "SetAirconCoolTemperature"
                ),
                "zoneId" if self._is_zone else "airconId": self._entity_id,
                "temperature": target_temp
            }]
        }

        # Optimistic update
        target = body.get("zones" if self._is_zone else "aircons", {}).get(self._entity_id, {})
        if mode == "heat":
            target["targetTemperatureHeat"] = target_temp
        elif mode == "cool":
            target["targetTemperatureCool"] = target_temp
        if self._is_zone:
            body["zones"][self._entity_id] = target
        else:
            body["aircons"][self._entity_id] = target
        self.coordinator.data["body"] = json.dumps(body)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode using verified working Command Array format."""
        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])

        if self._is_zone:
            if hvac_mode not in [HVACMode.AUTO, HVACMode.OFF]:
                return
            new_state = hvac_mode == HVACMode.AUTO
            command = {
                "commands": [{
                    "__type": "SetZoneOpenClose",
                    "zoneId": self._entity_id,
                    "isOpen": new_state
                }]
            }
            zone = body.get("zones", {}).get(self._entity_id, {})
            zone["isOn"] = new_state
            body["zones"][self._entity_id] = zone
            self._last_known_is_on = new_state
        else:
            commands = []
            if hvac_mode == HVACMode.OFF:
                commands.append({
                    "__type": "SetAirconOnOff",
                    "airconId": self._entity_id,
                    "isOn": False
                })
            else:
                commands.extend([
                    {
                        "__type": "SetAirconOnOff",
                        "airconId": self._entity_id,
                        "isOn": True
                    },
                    {
                        "__type": "SetAirconMode",
                        "airconId": self._entity_id,
                        "mode": (
                            "heat" if hvac_mode == HVACMode.HEAT else
                            "cool" if hvac_mode == HVACMode.COOL else
                            "dry" if hvac_mode == HVACMode.DRY else
                            "fan"
                        )
                    }
                ])
            command = {"commands": commands}
            
            aircon = body.get("aircons", {}).get(self._entity_id, {})
            aircon["isOn"] = hvac_mode != HVACMode.OFF
            self._last_known_is_on = hvac_mode != HVACMode.OFF
            if hvac_mode != HVACMode.OFF:
                aircon["mode"] = (
                    "heat" if hvac_mode == HVACMode.HEAT else
                    "cool" if hvac_mode == HVACMode.COOL else
                    "dry" if hvac_mode == HVACMode.DRY else
                    "fan"
                )
            body["aircons"][self._entity_id] = aircon

        self.coordinator.data["body"] = json.dumps(body)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode):
        """Set priority preset mode using verified working Command Array format."""
        if not self._is_zone or self._attr_preset_modes is None:
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])

        new_priority = preset_mode == PRESET_PRIORITY
        command = {
            "commands": [{
                "__type": "SetPriorityZone",
                "zoneId": self._entity_id,
                "priorityEnabled": new_priority
            }]
        }

        zone = body.get("zones", {}).get(self._entity_id, {})
        zone["isPriorityZone"] = new_priority
        zone["isPriorityZoneActive"] = new_priority
        body["zones"][self._entity_id] = zone
        self.coordinator.data["body"] = json.dumps(body)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan speed or auto mode contextually splitting cooling/heating path calls."""
        if self._is_zone:
            return

        data = self.coordinator.data
        if not isinstance(data, dict) or not data or "body" not in data:
            return
        body = json.loads(data["body"])
        aircon_state = body.get("aircons", {}).get(self._entity_id, {})
        mode = aircon_state.get("mode", "cool")

        # Context-routing condition: mode='heat' maps to Heat registers.
        # mode='cool', 'fan' (Fan Only), or 'dry' all map to Cool registers.
        mode_suffix = "Heat" if mode == "heat" else "Cool"
        
        commands = []
        if fan_mode == "auto":
            commands.append({
                "__type": f"SetAircon{mode_suffix}MyFanEnabled",
                "airconId": self._entity_id,
                "isEnabled": True
            })
        else:
            speed_map = {"low": 1, "medium": 2, "high": 3}
            speed = speed_map.get(fan_mode, 1)
            commands.append({
                "__type": f"SetAircon{mode_suffix}FanSpeed",
                "airconId": self._entity_id,
                "fanSpeed": speed
            })

        command = {"commands": commands}

        # Optimistic local state update map
        aircon = body.get("aircons", {}).get(self._entity_id, {})
        if fan_mode == "auto":
            aircon["isMyFanHeatingEnabled"] = (mode == "heat")
            aircon["isMyFanCoolingEnabled"] = (mode != "heat")
            aircon[f"fanSpeed{mode_suffix}"] = 3 
        else:
            aircon["isMyFanHeatingEnabled"] = False
            aircon["isMyFanCoolingEnabled"] = False
            aircon[f"fanSpeed{mode_suffix}"] = speed

        body["aircons"][self._entity_id] = aircon
        self.coordinator.data["body"] = json.dumps(body)
        self.async_write_ha_state()

        await self._myplaceiq.send_command(command)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
