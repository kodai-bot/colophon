COLOPHON — QUICK REFERENCE
==========================

To start: double-click launch.sh
          or run: ./scripts/launch.sh

MODES
-----
1. Counter    — daily sales scanning, all staff
2. Intake     — catalog, deliveries, prices and stock corrections
3. Payments   — room hire, memberships, and other sundry payments
4. Admin      — sales log, reports, reconciliation (PIN protected)

ADMIN PIN:  set in config/settings.yaml (look for "admin: pin:")

TO QUIT
-------
Ctrl+Q quits the whole program from any screen.
(Esc / Back only leaves the current mode, not the program.)

NON-ISBN ITEMS
--------------
Postcards, prints and other items without barcodes
are configured in config/settings.yaml
Open that file in a text editor to add or change items and prices.

DAILY REPORTS
-------------
Generated automatically at the time set in config/settings.yaml.
Sent to the office shared drive.
Also available locally in the sync/ folder if the network is down.

PROBLEMS?
---------
Contact whoever administers this system for your shop.

---
Copy this file to README_LAUNCH.txt and edit it for your own shop —
that copy is meant to be printed and kept by the till, so it should
have your actual PIN and contact details filled in, not placeholders.
