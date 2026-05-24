# Changelog

All notable changes to the MyPlaceIQ Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.3.0] - 2026-05-24
### Added
- Added control of Priorty zones, and moved sensors to be Binary sensors.

## [1.2.0] - 2026-05-09
### Added
- Changed step size of temperature from 1.0 to 0.5.

## [1.1.0] - 2025-10-17
### Added
- Ensure that climate entities are updated at the same time as the base entities and follow the same polling interval that is defined when configuring the integration.

### Fixed
- Fixed an [issue](https://github.com/anwickes/myplaceiq/issues/13) where the poller was not pulling the correct data from the myplaceiq hub. This subsequently fixes as issue where data is not being updated in home assistant after being modified externally (ie myplaceiq application).


## [1.0.0] - 2025-10-10
### Added
- First official release so contains all added functionality that has been mentioned in previous changelog updates.

### Fixed
- Resolved `AttributeError: 'ConfigEntry' object has no attribute '_update_listener'` in the options flow.
- Improved coordinator to correctly apply the `poll_interval` setting without resetting to default (60 seconds).

### Changed
- Updated `async_config_entry_first_refresh` to `async_refresh` to avoid deprecation warnings in Home Assistant 2025.11.


## [Unreleased] - 2025-10-04
### Added
- Climate entities for zones (e.g., `climate.main_bedroom_climate`) and main system (e.g., `climate.myplaceiq_system`).
- Support for temperature control (`SetZoneHeatTemperature`, `SetAirconHeatTemperature`, etc.) and HVAC modes (`heat`, `cool`, `dry`, `fan`, `off`).
- Integration with thermostat cards for temperature and mode control.
- Optimistic updates for temperature and mode changes.


## [Unreleased] - 2025-10-03
### Added
- Initial support for MyPlaceIQ HVAC hub.
- Sensor entities for zone states (e.g., `sensor.main_bedroom_state`).
- Button entities with optimistic updates (e.g., `button.main_bedroom_toggle`).
- Configuration via UI with host, port, client ID, client secret, and poll interval.
- Options flow to update all configuration fields.

### Changed
- N/A

### Fixed
- N/A
