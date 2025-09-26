#
#   gpuzone.py (C) 2020-2025, Peter Sulyok
#   smfc package: Super Micro fan control for Linux (home) servers.
#   smfc.GpuZone() class implementation.
#
import subprocess, glob
import time
import re
from configparser import ConfigParser
from typing import List
from smfc.fancontroller import FanController
from smfc.ipmi import Ipmi
from smfc.log import Log


class GpuZone(FanController):
    """Class for GPU zone fan control."""

    # GpuZone specific parameters.
    gpu_device_ids: List[int]  # GPU device IDs (indexes)
    gpu_temperature: List[float]  # List of GPU temperatures
    temp_retrieved: list[float]  # Last time temp was retrieved

    # Constant values for the configuration parameters.
    CS_GPU_ZONE: str = "GPU zone"
    CV_GPU_ZONE_ENABLED: str = "enabled"
    CV_GPU_IPMI_ZONE: str = "ipmi_zone"
    CV_GPU_ZONE_TEMP_CALC: str = "temp_calc"
    CV_GPU_ZONE_STEPS: str = "steps"
    CV_GPU_ZONE_SENSITIVITY: str = "sensitivity"
    CV_GPU_ZONE_POLLING: str = "polling"
    CV_GPU_ZONE_MIN_TEMP: str = "min_temp"
    CV_GPU_ZONE_MAX_TEMP: str = "max_temp"
    CV_GPU_ZONE_MIN_LEVEL: str = "min_level"
    CV_GPU_ZONE_MAX_LEVEL: str = "max_level"
    CV_GPU_ZONE_GPU_IDS: str = "gpu_device_ids"

    def __init__(self, log: Log, ipmi: Ipmi, config: ConfigParser) -> None:
        """Initialize the GpuZone class. Abort in case of configuration errors.
        Args:
            log (Log): reference to a Log class instance
            ipmi (Ipmi): reference to an Ipmi class instance
            config (configparser.ConfigParser): reference to the configuration (default=None)
        Raises:
            ValueError: invalid parameters
        """
        gpu_id_list: str  # String for gpu_device_ids=
        count: int  # GPU count.

        # Save and validate GpuZone class-specific parameters.
        gpu_id_list = config[self.CS_GPU_ZONE].get(self.CV_GPU_ZONE_GPU_IDS, "0")
        gpu_id_list = re.sub(" +", " ", gpu_id_list.strip())
        try:
            self.gpu_device_ids = [
                int(s) for s in gpu_id_list.split("," if "," in gpu_id_list else " ")
            ]
        except ValueError as e:
            raise e
        for gid in self.gpu_device_ids:
            if gid not in range(0, 101):
                raise ValueError(
                    f"invalid value: {self.CV_GPU_ZONE_GPU_IDS}={gpu_id_list}."
                )
        count = len(self.gpu_device_ids)
        self.temp_retrieved: list[float] = [0 for _ in range(count)]
        self.gpu_temperature: list[float] = [0 for _ in range(count)]

        # Initialize FanController class.
        super().__init__(
            log,
            ipmi,
            config[GpuZone.CS_GPU_ZONE].get(
                GpuZone.CV_GPU_IPMI_ZONE, fallback=f"{Ipmi.HD_ZONE}"
            ),
            GpuZone.CS_GPU_ZONE,
            count,
            config[GpuZone.CS_GPU_ZONE].getint(
                GpuZone.CV_GPU_ZONE_TEMP_CALC, fallback=FanController.CALC_AVG
            ),
            config[GpuZone.CS_GPU_ZONE].getint(GpuZone.CV_GPU_ZONE_STEPS, fallback=5),
            config[GpuZone.CS_GPU_ZONE].getfloat(
                GpuZone.CV_GPU_ZONE_SENSITIVITY, fallback=2
            ),
            config[GpuZone.CS_GPU_ZONE].getfloat(
                GpuZone.CV_GPU_ZONE_POLLING, fallback=2
            ),
            config[GpuZone.CS_GPU_ZONE].getfloat(
                GpuZone.CV_GPU_ZONE_MIN_TEMP, fallback=40
            ),
            config[GpuZone.CS_GPU_ZONE].getfloat(
                GpuZone.CV_GPU_ZONE_MAX_TEMP, fallback=70
            ),
            config[GpuZone.CS_GPU_ZONE].getint(
                GpuZone.CV_GPU_ZONE_MIN_LEVEL, fallback=35
            ),
            config[GpuZone.CS_GPU_ZONE].getint(
                GpuZone.CV_GPU_ZONE_MAX_LEVEL, fallback=100
            ),
        )

        # Print configuration in CONFIG log level (or higher).
        if self.log.log_level >= Log.LOG_CONFIG:
            self.log.msg(
                Log.LOG_CONFIG, f"   {self.CV_GPU_ZONE_GPU_IDS} = {self.gpu_device_ids}"
            )

    def _get_nth_temp(self, index: int) -> float:
        """Get the temperature of the nth element in the GPU device list.
        Args:
            index (int): index in GPU device list
        Returns:
            float: temperature value
        Raises:
            FileNotFoundError:  file or command cannot be found
            ValueError:         invalid temperature value
            IndexError:         invalid index
        """
        current_time = time.monotonic()
        if (current_time - self.temp_retrieved[index]) >= self.polling:
            r: subprocess.CompletedProcess  # result of the executed process

            try:
                paths = glob.glob(
                    f"/sys/class/drm/card{self.gpu_device_ids[index]}/device/hwmon/*/temp*_input"
                )
                if not paths:
                    raise FileNotFoundError("No hwmon temp*_input files found")

                args = ["grep", ".", *paths]
                r = subprocess.run(args, check=False, capture_output=True, text=True)
            except FileNotFoundError as e:
                raise e

            self.temp_retrieved[index] = current_time
            temp_list = r.stdout.splitlines()
            temp_list = [float(temp.split(":")[1]) / 1000 for temp in temp_list]
            print(f"card{self.gpu_device_ids[index]}: {temp_list=}")
            self.gpu_temperature[index] = max(temp_list)

        return self.gpu_temperature[index]


# End.
