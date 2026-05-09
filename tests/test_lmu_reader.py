"""Unit tests for LMUReader — runnable on macOS/Linux via mocking."""

from unittest.mock import patch, MagicMock


def test_lmu_reader_unavailable_when_import_fails():
    """If pyRfactor2SharedMemory cannot be imported, the reader should
    set available=False and read()/is_connected() should return safely."""
    # Force import failure inside __init__ by patching the module's import.
    with patch.dict('sys.modules', {'pyRfactor2SharedMemory.sharedMemoryAPI': None}):
        from s1napse.readers.lmu import LMUReader
        # Re-instantiating should hit the except path because the patched
        # entry forces ImportError on `from ... import ...`.
        reader = LMUReader()
        assert reader.available is False
        assert reader.read() is None
        assert reader.is_connected() is False
