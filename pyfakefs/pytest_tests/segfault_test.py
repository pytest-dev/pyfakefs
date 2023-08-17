"""
This is a regression test for #866 that shall ensure that
shutting down the test session after this specific call does not result
in a segmentation fault.
"""
import opentimelineio as otio


def test_empty_fs(fs):
    pass


def test_create_clip(fs):
    """If the fs cache is not cleared during session shutdown, a segmentation fault
    will happen during garbage collection of the cached modules."""
    otio.core.SerializableObjectWithMetadata(metadata={})
