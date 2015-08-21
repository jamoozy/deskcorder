# Deskcorder #

Deskcorder is a recorder for what happens at your desk.


---


# Important Note: trunk intentionally broken #
Currently `trunk` is broken.  This is intentional, as we are undergoing major changes internal to the basic data structure (`Lecture` et al.).  If you would like a version of the code to play around with, please download from `http://deskcorder.googlecode.com/svn/tags/v0.1` (https also supported for project members) instead of the default location.

## Current State ##
Recording and playback finally work again (mostly).  File I/O is still pretty broken ... DCB v0.2.0 seems okay-ish ... still untested.

Sorry for the inconvenience.  We're working on getting `trunk` happy again soon!

-jam-


---


# Uses #

Deskcorder is meant to record ideas into a portable format.  As of v0.1 it supports PDF and Flash to limited degrees.  Deskcorder "stores ideas" by synchronizing drawn and spoken media and allowing their playback.

Originally Deskcorder was used by Alawi to help him in his capacity as a TA.  Whenever he noticed many of his students were missing the same problem or making the same mistake, he would create a Deskcorder Flash file and post it online.  Each of these files would be on the order of 5 minutes, and so were quick to watch.  The students seemed to benefit from viewing these mini tutorials.

With v0.2 we're hoping Deskcorder will be able to record entire university classroom lectures (of up to 3 hours).  This would negate the need for students to copy down the board at all.  Additional "ideal" features include some simple text-to-speech capability that would allow automatic transcription of lectures, perhaps in PDF files.