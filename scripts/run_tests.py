"""Run the complete suite with a stack dump if a native Qt operation stalls."""
import faulthandler
import unittest


def main():
    # A C++ geometry stall otherwise occupies the entire 45-minute build job.
    # Exit nonzero with its Python call site; every test still has to pass.
    faulthandler.dump_traceback_later(300, exit=True)
    try:
        unittest.main(module=None, argv=['unittest', 'discover', '-v'])
    finally:
        faulthandler.cancel_dump_traceback_later()


if __name__ == '__main__':
    main()
