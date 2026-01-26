📦 HabZone – EDMC 6.x Compatibility Update

Version: 1.20-edmc6
Status: Stable
Tested with: EDMarketConnector 6.1.1, Python 3.13

🔧 Changes

Updated Config API for EDMC 6.x

config.getint() → config.get_int()

Updated Locale API

Locale.stringFromNumber() → Locale.string_from_number()

Fixed silent failures during Scan events

Added safe debug logging (print_exc() in debug mode)

Improved robustness for missing journal fields

No functional behavior changes to HabZone calculations

✅ Result

Plugin loads cleanly in EDMC 6.x

Habitable Zone distances display correctly after scanning the arrival star

Fully compatible with modern Python 3.x builds

ℹ️ Notes

This update is a maintenance / compatibility fix only

Original functionality and UI layout are unchanged

Safe drop-in replacement for the original HabZone-master/load.py

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
