"""Handle persistence."""
import json
import logging
import os
import pickle

from .sensor import ChildSensor, Sensor

_LOGGER = logging.getLogger(__name__)


class Persistence:
    """Organize persistence file saving and loading."""

    def __init__(self, sensors, schedule_factory, persistence_file="mysensors.pickle"):
        """Set up Persistence instance."""
        self._sensors = sensors
        self.need_save = True
        self.persistence_file = persistence_file
        self.persistence_bak = "{}.bak".format(self.persistence_file)
        self.schedule_save_sensors = schedule_factory(self.save_sensors)

    def _save_pickle(self, filename):
        """Save sensors to pickle file."""
        with open(filename, "wb") as file_handle:
            pickle.dump(self._sensors, file_handle, pickle.HIGHEST_PROTOCOL)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    def _load_pickle(self, filename):
        """Load sensors from pickle file."""
        with open(filename, "rb") as file_handle:
            self._sensors.update(pickle.load(file_handle))

    def _save_json(self, filename):
        """Save sensors to json file."""
        with open(filename, "w") as file_handle:
            json.dump(self._sensors, file_handle, cls=MySensorsJSONEncoder, indent=4)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    def _load_json(self, filename):
        """Load sensors from json file."""
        with open(filename, "r") as file_handle:
            self._sensors.update(json.load(file_handle, cls=MySensorsJSONDecoder))

    def save_sensors(self):
        """Save sensors to file."""
        if not self.need_save:
            return
        fname = os.path.realpath(self.persistence_file)
        exists = os.path.isfile(fname)
        dirname = os.path.dirname(fname)
        if not os.access(dirname, os.W_OK) or exists and not os.access(fname, os.W_OK):
            _LOGGER.error("Permission denied when writing to %s", fname)
            return
        split_fname = os.path.splitext(fname)
        tmp_fname = "{}.tmp{}".format(split_fname[0], split_fname[1])
        _LOGGER.debug("Saving sensors to persistence file %s", fname)
        self._perform_file_action(tmp_fname, "save")
        if exists:
            os.rename(fname, self.persistence_bak)
        os.rename(tmp_fname, fname)
        if exists:
            os.remove(self.persistence_bak)
        self.need_save = False

    def _load_sensors(self, path=None):
        """Load sensors from file."""
        if path is None:
            path = self.persistence_file
        exists = os.path.isfile(path)
        if exists and os.access(path, os.R_OK):
            if path == self.persistence_bak:
                os.rename(path, self.persistence_file)
                path = self.persistence_file
            _LOGGER.debug("Loading sensors from persistence file %s", path)
            self._perform_file_action(path, "load")
            return True
        _LOGGER.warning("File does not exist or is not readable: %s", path)
        return False

    def safe_load_sensors(self):
        """Load sensors safely from file."""
        try:
            loaded = self._load_sensors()
        except (EOFError, ValueError):
            _LOGGER.error("Bad file contents: %s", self.persistence_file)
            loaded = False
        if not loaded:
            _LOGGER.warning("Trying backup file: %s", self.persistence_bak)
            try:
                if not self._load_sensors(self.persistence_bak):
                    _LOGGER.warning(
                        "Failed to load sensors from file: %s", self.persistence_file
                    )
            except (EOFError, ValueError):
                _LOGGER.error("Bad file contents: %s", self.persistence_file)
                _LOGGER.warning("Removing file: %s", self.persistence_file)
                os.remove(self.persistence_file)

    def _perform_file_action(self, filename, action):
        """Perform action on specific file types.

        Dynamic dispatch function for performing actions on
        specific file types.
        """
        ext = os.path.splitext(filename)[1]
        try:
            func = getattr(self, "_{}_{}".format(action, ext[1:]))
        except AttributeError:
            raise Exception("Unsupported file type {}".format(ext[1:]))
        func(filename)


class MySensorsJSONEncoder(json.JSONEncoder):
    """JSON encoder."""

    def default(self, obj):
        """Serialize obj into JSON."""
        # pylint: disable=method-hidden, protected-access, arguments-differ
        if isinstance(obj, Sensor):
            return {
                "sensor_id": obj.sensor_id,
                "children": obj.children,
                "type": obj.type,
                "sketch_name": obj.sketch_name,
                "sketch_version": obj.sketch_version,
                "battery_level": obj.battery_level,
                "protocol_version": obj.protocol_version,
                "heartbeat": obj.heartbeat,
            }
        if isinstance(obj, ChildSensor):
            return {
                "id": obj.id,
                "type": obj.type,
                "description": obj.description,
                "values": obj.values,
            }
        return json.JSONEncoder.default(self, obj)


class MySensorsJSONDecoder(json.JSONDecoder):
    """JSON decoder."""

    def __init__(self):
        """Set up decoder."""
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object)

    def dict_to_object(self, obj):  # pylint: disable=no-self-use
        """Return object from dict."""
        if not isinstance(obj, dict):
            return obj
        if "sensor_id" in obj:
            sensor = Sensor(obj["sensor_id"])
            for key, val in obj.items():
                setattr(sensor, key, val)
            return sensor
        if all(k in obj for k in ["id", "type", "values"]):
            child = ChildSensor(obj["id"], obj["type"], obj.get("description", ""))
            child.values = obj["values"]
            return child
        if all(k.isdigit() for k in obj.keys()):
            return {int(k): v for k, v in obj.items()}
        return obj
