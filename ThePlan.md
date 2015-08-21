# Introduction #

Since v0.1 of deskcorder (anonymous checkout: `svn co http://deskcorder.googlecode.com/svn/tags/v0.1`) we noticed there were several things we wanted to do that weren't possible.  So we made a plan for v0.2 of Deskcorder.  That plan is (at least in part) written below.

# Feature Additions #
We want to add several features that other programs have and so should we.

  * Add a configuration file in "the default place"
  * Implement PDF import.
  * Add slide manager feature, that allows you to go back to a slide to add on to it or put that slide as the background.
  * Undo/redo features
  * Erasers that are:
    * Much thicker which brushes.
    * An "erase stroke" tool, like in Xournal

# File Format Changes #
We have identified a couple areas where our purposes could be better served with an "easier" file format.

## Current Format ##
Currently we have only one file format that is really fully supported and used:

  1. A "DCB" (Deskcorder Binary) file format, which stores the entire lecture in a single file.

## Additional Formats ##

Since this is good for research code, it would be nice to have a more transparent save file format.  In other words, it would be good to be able to use existing tools to edit/manipulate Deskcorder files.  The way we propose to do this, is to create a couple new file formats:

  1. A "DCD" (Deskcorder Directory) "file" format, which takes advantage of the hierarchical nature of a lecture by mapping it to a directory tree.
  1. A "DAR" (Deskcorder Archive) file format, which is the same as above, except tar-gzipped into a single file.

These will be stored in a directory thusly:

  * **Top Level**: named something like `session` or `lecture`
    * **Slides**: each slide has its own sub-directory.
      * There's a `metadata` file that holds the unix time the slide was created.
      * **Strokes**: Each stroke is stored in a `strokeXXX` file in DCB file format.
    * **Moves**: Next come moves so that all mouse movements are incorporated.
    * **Audio**: Next come audio files.

Major benefits:
  1. This format can then be manipulated with well-established command-line tools.
  1. This format is very extensible: just add things into the directory.

Further, this type of format (using the disk) will allow _long_ lectures to be created without having to keep everything in RAM.  It can just be written to disk at the end of every slide.  **Additionally**, this will serve as our own built-in crash recovery thing.

# Iterators #

With the new file format changes, it will be imperative that a `Lecture.Iterator` be made that hits the disk.  Does this necessitate there be multiple kinds of `Lecture`?  Maybe.