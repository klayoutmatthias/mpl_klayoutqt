
# A matplotlib backend demonstrator using KLayout/Qt instead of PyQt 

This sample code is a hacked version of the original code from
https://github.com/matplotlib/matplotlib, PyQt5 backend ("QtAgg").
Reference code version is:
https://github.com/matplotlib/matplotlib/tree/17db60b4de127347b319e60a7ae24224efbea09e

It needs an experimental KLayout version (as of writing) which supplies
the QImage constructor taking binary pixel data.
A suitable version is this: https://github.com/KLayout/klayout/tree/0cae15c6fa60572b623b2c09441b3a2a2609a4aa.

To try it, make sure this tree is in `$KLAYOUT_PYTHONPATH` and
use the "matplotlib.lym" macro as an example.

TODO:
* Editor functions are not translated (because of license)
* Code needs some cleanup

