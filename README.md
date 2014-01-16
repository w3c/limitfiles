# limitfiles

Some tools regularly create new files, and never clean them up.  limitfiles uses inotify to keep them from getting out of hand.

## Dependencies

Python 3.1+ and [pyinotify](https://github.com/seb-m/pyinotify).

## Installation

    # python3 setup.py install
    
## Configuration

limitfiles reads sections like this from `/etc/limitfiles.ini`:

    [Example]
    directory=/tmp/example
    keep=20
    max=40
    match=\.log$
    
The section name is the name for this watch; you can use whatever you like.

`directory` is the directory to watch with inotify.  If you specify a Python regular expression as `match`, limitfiles will only keep track of files with matching names.

When the count of watched files hits the number in `max`, limitfiles will delete the oldest ones until it gets down to the number in `keep`.

You can define as many sections like this as you need.

## Usage

Refer to the pydoc for command-line options and module documentation.

## Contact

<brett@w3.org>
