📦 HabZone – EDMC 6.x Compatibility Update

Version: 1.22-edmc6
Status: Stable
Tested with: EDMarketConnector 6.1.1, Python 3.13

🧭 HabZone – Changelog
v1.20-edmc6-slim

EDMC 6.x compatible – refactored & streamlined release

✨ New

Automatic restore after EDMC restart
Habitable Zone distances are now restored automatically after restarting EDMC, without requiring a system jump.

Journal-based startup detection
The plugin determines the current system on startup by parsing the latest Elite Dangerous journal file, ensuring reliable restore behavior.

Optional verbose logging
Added a preference to enable detailed logging for troubleshooting (disabled by default).

🔧 Improved

Slimmed-down codebase
Significant refactor to reduce complexity and maintenance overhead while preserving full functionality.

Modernized EDMC 6.x focus
Removed legacy Python 2 compatibility and unused imports to align fully with EDMC 6.x.

Cleaner internal state handling
Simplified persistence and restore logic for better robustness and readability.

UI formatting polish

Consistent default font usage

Optional k / M abbreviation for large distances

Tooltips show exact distances on hover

Stable column widths to prevent UI jitter

🛠 Fixed

Missing data after EDMC restart
Distances are now shown immediately after restart when remaining in the same system.

Silent restore failures
Restore logic is now deterministic and easier to debug when verbose logging is enabled.

🧹 Removed

Legacy Python 2 fallback code

Unused imports and dead code paths

Redundant configuration helpers and state variables

⚠️ Notes

This version is intended for EDMC 6.x and Python 3 only.

Users upgrading from older HabZone versions should remove or disable previous plugin folders to avoid conflicts.
----- Original - by Marginal -----

# Habitable Zone plugin for [EDMC](https://github.com/Marginal/EDMarketConnector/wiki)

This plugin helps explorers find high-value planets. It displays the "habitable-zone" (i.e. the range of distances in which you might find an Earth-Like World) when you scan the primary star in a system with a [Detailed Surface Scanner](http://elite-dangerous.wikia.com/wiki/Detailed_Surface_Scanner).

![Screenshot](img/screenie.png)

Optionally, you can choose to display the ranges in which you might find other high-value planets - Metal-Rich, Water and/or Ammonia Worlds.

Optionally, you can choose to display the high-value planets known to [Elite Dangerous Star Map](https://www.edsm.net/).

## Installation

* On EDMC's Plugins settings tab press the “Open” button. This reveals the `plugins` folder where EDMC looks for plugins.
* Download the [latest release](https://github.com/Marginal/HabZone/releases/latest).
* Open the `.zip` archive that you downloaded and move the `HabZone` folder contained inside into the `plugins` folder.

You will need to re-start EDMC for it to notice the new plugin.

## Acknowledgements

Calculations taken from Jackie Silver's [Hab-Zone Calculator](https://forums.frontier.co.uk/showthread.php?p=5452081).

## License

Copyright © 2017 Jonathan Harris.

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
