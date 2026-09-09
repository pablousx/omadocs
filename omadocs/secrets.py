"""Secret Service only. Values and third-party exception messages never escape."""
import json
import threading
from contextlib import closing, contextmanager
from . import PLUGIN_ID
from .errors import Fault


class Keyring:
    def __init__(self):
        self.lock = threading.RLock()

    @contextmanager
    def _collection(self):
        import secretstorage
        with closing(secretstorage.dbus_init()) as connection:
            collection = secretstorage.get_default_collection(connection)
            if collection.is_locked():
                collection.unlock()
            if collection.is_locked():
                raise Fault("keyring")
            yield collection

    def get(self, key):
        with self.lock:
            try:
                with self._collection() as collection:
                    for item in collection.search_items({"application": PLUGIN_ID, "key": key}):
                        if item.is_locked():
                            raise Fault("keyring")
                        value = json.loads(item.get_secret().decode("utf-8"))
                        return value
                return None
            except Exception:
                raise Fault("keyring") from None

    def put(self, key, value):
        with self.lock:
            try:
                with self._collection() as collection:
                    collection.create_item("omadocs credential", {"application": PLUGIN_ID, "key": key},
                                           json.dumps(value).encode("utf-8"), replace=True,
                                           content_type="application/json")
            except Exception:
                raise Fault("keyring") from None

    def delete(self, key):
        with self.lock:
            try:
                with self._collection() as collection:
                    for item in collection.search_items({"application": PLUGIN_ID, "key": key}):
                        item.delete()
            except Exception:
                raise Fault("keyring") from None

    def delete_all(self):
        with self.lock:
            try:
                with self._collection() as collection:
                    for item in collection.search_items({"application": PLUGIN_ID}):
                        item.delete()
            except Exception:
                raise Fault("keyring") from None
