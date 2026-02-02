# 📦 HabZone – [EDMC](https://github.com/EDCD/EDMarketConnector/wiki) 6.x Compatibility Update

This plugin helps explorers find high-value planets. It displays the "habitable-zone" (i.e. the range of distances in which you might find an Earth-Like World) when you scan the primary star in a system with a [Detailed Surface Scanner](http://elite-dangerous.wikia.com/wiki/Detailed_Surface_Scanner).

Version: 1.23-edmc6
Status: Stable
Tested with: EDMarketConnector 6.1.1, Python 3.13

# New
v1.23
- Auto-rescan on EDMC startup (Journal restore + optional EDSM refresh)
- manual "Rescan" button

v1.22
- remove decimals in distance display
- optional k/M abbreviation for large distances (toggle in prefs)
- tooltip shows exact distance when abbreviation is enabled

## Installation

* On EDMC's Plugins settings tab press the “Open” button. This reveals the `plugins` folder where EDMC looks for plugins.
* Download the [latest release](https://github.com/R4m8o/HabZone-edmc6/releases/latest).
* Open the `.zip` archive that you downloaded and move the `HabZone` folder contained inside into the `plugins` folder.

You will need to re-start EDMC for it to notice the new plugin.

# ℹ️ Notes

This update is a maintenance / compatibility fix only

Original functionality and UI layout are unchanged

Safe drop-in replacement for the original HabZone-master/load.py

----- Original - by Marginal -----

![Screenshot](img/screenie.png)

Optionally, you can choose to display the ranges in which you might find other high-value planets - Metal-Rich, Water and/or Ammonia Worlds.

Optionally, you can choose to display the high-value planets known to [Elite Dangerous Star Map](https://www.edsm.net/).

## Acknowledgements

Calculations taken from Jackie Silver's [Hab-Zone Calculator](https://forums.frontier.co.uk/showthread.php?p=5452081).

## License

Copyright © 2017 Jonathan Harris.

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
