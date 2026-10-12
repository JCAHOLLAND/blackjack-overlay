# Adrian Kennard standard playing-card deck

Author: Adrian Kennard (RevK)
Source and license declaration: https://www.me.uk/cards/
Standard deck view: https://www.me.uk/cards/makeadeck.cgi?view=
Downloaded SVG ZIP: https://www.me.uk/cards/makeadeck.cgi?zip=
Download date: 12 October 2026.
License: CC0 1.0 Universal Public Domain Dedication.
https://creativecommons.org/publicdomain/zero/1.0/
Full legal text is in LICENSE.txt.

The author's page states that the court cards are based on 19th-century Goodall & Son designs. This is the site's standard deck, without ghost, super-index or custom settings. No Bicycle trademarks or branding were added. The black diamond-pattern back is the standard 1B.svg design.

All 56 downloaded SVG files are included unmodified in svg/: 52 standard faces, two jokers and two backs. The blackjack runtime uses the 52 faces plus 1B.svg. Original ace-of-spades author text is retained.

Mapping: SVG rank A/2..9/T/J/Q/K maps to Ace/2..9/10/Jack/Queen/King; suits C/D/H/S map to clubs/diamonds/hearts/spades. 1B.svg maps to back.png.

Derived PNG animation atlases preserve 5:7 proportions and transparent rounded corners. SVG rasterization used Sharp/librsvg during preparation only. Antialiased resize and horizontal squeeze frames were prepared using Pillow during preparation only. Each PNG atlas is 64 pixels wide with 123 rows of 88 pixels: 30 normal resize frames, 31 hole-card reveal frames, 31 large-card deal flips and 31 small-card deal flips. Runtime only requires Python and Tkinter.
